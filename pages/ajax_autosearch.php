<?php
define('__ROOT__', dirname(dirname(__FILE__)));
define('pvault_panel', TRUE);

require_once(__ROOT__.'/inc/sec.php');      // Session & Security (initializes $userID)
require_once(__ROOT__.'/inc/opendb.php');   // Database Connection (initializes $conn)
require_once(__ROOT__.'/inc/settings.php'); // Settings

// This file serves as the strict internal endpoint for the frontend
// It bypasses the public API's "administratively disabled" checks because
// we rely on sec.php (user session) for authentication/authorization.

require_once(__ROOT__.'/api-functions/ingredient_autosearch.php');
?>
