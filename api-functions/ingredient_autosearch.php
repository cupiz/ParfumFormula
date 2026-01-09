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
    $notes = 'Auto-imported from: ' . implode(', ', $ing['sources'] ?? ['Online']);
    $notes = mysqli_real_escape_string($conn, $notes);
    
    // Insert ingredient
    $sql = "INSERT INTO ingredients (
        name, cas, INCI, formula, molecularWeight, cid, profile, notes, owner_id, created_at
    ) VALUES (
        '$name', '$cas', '$iupac', '$formula', '$molecularWeight', $cid, '$profile', '$notes', '$userID', NOW()
    )";
    
    $result = mysqli_query($conn, $sql);
    
    if ($result) {
        $newId = mysqli_insert_id($conn);
        
        // Also add to IFRA library check if CAS exists
        if (!empty($cas)) {
            syncWithIFRA($conn, $userID, $cas, $name);
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
 * Sync with IFRA library if entry exists
 */
function syncWithIFRA($conn, $userID, $cas, $name) {
    $cas = mysqli_real_escape_string($conn, $cas);
    
    // Check if IFRA entry exists for this CAS
    $ifra = mysqli_query($conn, "SELECT * FROM IFRALibrary WHERE cas = '$cas' AND owner_id = '$userID'");
    
    if (mysqli_num_rows($ifra) > 0) {
        // IFRA entry exists, ingredient will automatically use it
        error_log("PV Info: IFRA entry found for $name (CAS: $cas)");
    }
}
?>
