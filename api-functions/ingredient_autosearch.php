<?php
/**
 * Ingredient Auto-Search API Bridge
 * 
 * This endpoint bridges the PHP frontend with the Python automation API
 * to search for ingredients online when not found locally.
 * 
 * Endpoints:
 *   GET  ?action=search&name=xxx  - Search online sources
 *   POST ?action=add              - Add ingredient to database
 */

if (!defined('pvault_panel')){ die('Not Found'); }

header('Content-Type: application/json; charset=utf-8');

global $conn, $userID;

// Get automation API URL from environment or use default
$automationApiUrl = getenv('AUTOMATION_API_URL') ?: 'http://automation:5001';

$action = $_GET['action'] ?? $_POST['action'] ?? '';

switch ($action) {
    case 'search':
        handleSearch($automationApiUrl);
        break;
    case 'add':
        handleAdd($automationApiUrl, $conn, $userID);
        break;
    default:
        echo json_encode([
            'success' => false,
            'error' => 'Invalid action. Use "search" or "add".'
        ]);
}

/**
 * Handle ingredient search via automation API
 */
function handleSearch($apiUrl) {
    $name = trim($_GET['name'] ?? '');
    
    if (empty($name)) {
        http_response_code(400);
        echo json_encode([
            'success' => false,
            'error' => 'Missing ingredient name'
        ]);
        return;
    }
    
    // Call automation API
    $url = $apiUrl . '/search?' . http_build_query(['name' => $name]);
    
    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL => $url,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 60,  // Allow time for scraping
        CURLOPT_HTTPHEADER => ['Accept: application/json']
    ]);
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error = curl_error($ch);
    curl_close($ch);
    
    if ($error) {
        http_response_code(500);
        echo json_encode([
            'success' => false,
            'error' => 'Automation API connection failed: ' . $error
        ]);
        return;
    }
    
    // Forward the response
    http_response_code($httpCode);
    echo $response;
}

/**
 * Handle adding searched ingredient to database
 */
function handleAdd($apiUrl, $conn, $userID) {
    $data = json_decode(file_get_contents('php://input'), true);
    
    if (!$data || empty($data['ingredient'])) {
        http_response_code(400);
        echo json_encode([
            'success' => false,
            'error' => 'Missing ingredient data'
        ]);
        return;
    }
    
    $ing = $data['ingredient'];
    
    // Validate required fields
    if (empty($ing['name'])) {
        http_response_code(400);
        echo json_encode([
            'success' => false,
            'error' => 'Ingredient name is required'
        ]);
        return;
    }
    
    // Check if ingredient already exists
    $name = mysqli_real_escape_string($conn, $ing['name']);
    $check = mysqli_query($conn, "SELECT id FROM ingredients WHERE name = '$name' AND owner_id = '$userID'");
    
    if (mysqli_num_rows($check) > 0) {
        echo json_encode([
            'success' => false,
            'error' => 'Ingredient already exists in your library'
        ]);
        return;
    }
    
    // Prepare data for insertion
    $cas = mysqli_real_escape_string($conn, $ing['cas'] ?? '');
    $formula = mysqli_real_escape_string($conn, $ing['formula'] ?? '');
    $molecularWeight = mysqli_real_escape_string($conn, $ing['molecular_weight'] ?? '');
    $iupac = mysqli_real_escape_string($conn, $ing['iupac_name'] ?? '');
    $cid = intval($ing['cid'] ?? 0);
    $profile = mysqli_real_escape_string($conn, $ing['odor_description'] ?? '');
    $femaRaw = $ing['fema'] ?? '';
    // Strip "FEMA " prefix and any whitespace, keeping only numbers
    $fema = preg_replace('/[^0-9]/', '', $femaRaw);
    $fema = mysqli_real_escape_string($conn, $fema);
    
    // Map extracted fields
    $flash_point = mysqli_real_escape_string($conn, $ing['flash_point'] ?? '');
    $appearance = mysqli_real_escape_string($conn, $ing['appearance'] ?? '');
    $strengthRaw = $ing['odor_strength'] ?? 'Medium';
    $strength = mysqli_real_escape_string($conn, $strengthRaw);
    
    // New fields
    $tenacity = mysqli_real_escape_string($conn, $ing['tenacity'] ?? '');
    $logp = mysqli_real_escape_string($conn, $ing['logp'] ?? '');
    $soluble = mysqli_real_escape_string($conn, $ing['solubility'] ?? '');
    $einecs = mysqli_real_escape_string($conn, $ing['einecs'] ?? '');
    $reach = mysqli_real_escape_string($conn, $ing['reach'] ?? '');
    
    // Shelf Life extraction (convert "24.00 month(s)" to integer "24")
    $shelfLifeRaw = $ing['shelf_life'] ?? '0';
    preg_match('/(\d+)/', $shelfLifeRaw, $matches);
    $shelf_life = isset($matches[1]) ? intval($matches[1]) : 0;
    
    // Physical State: API returns 1 (Liquid) or 2 (Solid) based on appearance
    // If API is null, default to 1 (Liquid)
    $physical_state = intval($ing['physical_state'] ?? 1);
    
    // Defaults & Mapping
    // Valid values for type: AC, EO, Other/Unknown, Custom Blend, Carrier, Solvent, Base
    $type = 'AC';             

    $allergen = 0;
    
    // Map API fields
    $profileVal = 'Heart'; 
    
    // PV 'notes' is the Odor Description
    $odorDesc = $ing['odor_description'] ?? '';
    // Append Tenacity or other notes if we extracted them (future proofing)
    $notes = mysqli_real_escape_string($conn, $odorDesc);
    
    $sourceNote = 'Auto-imported from: ' . implode(', ', $ing['sources'] ?? ['Online']);
    if($notes) {
        $notes .= "\n\n" . $sourceNote;
    } else {
        $notes = $sourceNote;
    }
    
    // Insert ingredient
    $sql = "INSERT INTO ingredients (
        name, cas, INCI, formula, molecularWeight, cid, profile, notes, FEMA, type, strength, physical_state, allergen, flash_point, appearance, tenacity, logp, soluble, shelf_life, einecs, reach, owner_id, created_at
    ) VALUES (
        '$name', '$cas', '$iupac', '$formula', '$molecularWeight', $cid, '$profileVal', '$notes', '$fema', '$type', '$strength', '$physical_state', '$allergen', '$flash_point', '$appearance', '$tenacity', '$logp', '$soluble', '$shelf_life', '$einecs', '$reach', '$userID', NOW()
    )";
    
    $result = mysqli_query($conn, $sql);
    
    if ($result) {
        $newId = mysqli_insert_id($conn);
        
        // Also add to IFRA library check if CAS exists
        if (!empty($cas)) {
            syncWithIFRA($conn, $userID, $cas, $name, $newId);
        }
        
        echo json_encode([
            'success' => true,
            'message' => 'Ingredient added to your library',
            'ingredient_id' => $newId,
            'name' => $ing['name']
        ]);
    } else {
        http_response_code(500);
        echo json_encode([
            'success' => false,
            'error' => 'Database error: ' . mysqli_error($conn)
        ]);
    }
}

/**
 * Sync with IFRA library and UPDATE ingredients table usage limits
 */
function syncWithIFRA($conn, $userID, $cas, $name, $ingID) {
    $cas = mysqli_real_escape_string($conn, $cas);
    
    // Check if IFRA entry exists for this CAS
    $ifraQuery = mysqli_query($conn, "SELECT * FROM IFRALibrary WHERE cas = '$cas' AND owner_id = '$userID'");
    
    if ($row = mysqli_fetch_array($ifraQuery)) {
        // IFRA entry exists, now we MUST update the ingredient's usage limits
        error_log("PV Info: Syncing IFRA limits for $name (CAS: $cas)");

        $cat1 = $row['cat1'] ?? 100;
        $cat2 = $row['cat2'] ?? 100;
        $cat3 = $row['cat3'] ?? 100;
        $cat4 = $row['cat4'] ?? 100;
        $cat5A = $row['cat5A'] ?? 100;
        $cat5B = $row['cat5B'] ?? 100;
        $cat5C = $row['cat5C'] ?? 100;
        $cat5D = $row['cat5D'] ?? 100;
        $cat6 = $row['cat6'] ?? 100;
        $cat7A = $row['cat7A'] ?? 100;
        $cat7B = $row['cat7B'] ?? 100;
        $cat8 = $row['cat8'] ?? 100;
        $cat9 = $row['cat9'] ?? 100;
        $cat10A = $row['cat10A'] ?? 100;
        $cat10B = $row['cat10B'] ?? 100;
        $cat11A = $row['cat11A'] ?? 100;
        $cat11B = $row['cat11B'] ?? 100;
        $cat12 = $row['cat12'] ?? 100;
        
        // Update the ingredient record with these limits
        $updateSql = "UPDATE ingredients SET 
            cat1 = '$cat1', cat2 = '$cat2', cat3 = '$cat3', cat4 = '$cat4', 
            cat5A = '$cat5A', cat5B = '$cat5B', cat5C = '$cat5C', cat5D = '$cat5D',
            cat6 = '$cat6', cat7A = '$cat7A', cat7B = '$cat7B', cat8 = '$cat8',
            cat9 = '$cat9', cat10A = '$cat10A', cat10B = '$cat10B',
            cat11A = '$cat11A', cat11B = '$cat11B', cat12 = '$cat12',
            allergen = 1  -- Mark as allergen since it has IFRA entry
            WHERE id = '$ingID' AND owner_id = '$userID'";
            
        mysqli_query($conn, $updateSql);
    }
}
?>
