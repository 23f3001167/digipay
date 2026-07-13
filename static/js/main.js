document.addEventListener('DOMContentLoaded', function() {
    // Select all alerts that are meant to be dismissible
    const allAlerts = document.querySelectorAll('.alert-dismissible');

    allAlerts.forEach(function(alertElement) {
        // Set a timeout to close the alert
        setTimeout(function() {
            // Use Bootstrap's built-in Alert instance to close it
            // This ensures a proper fade-out animation
            const bsAlert = new bootstrap.Alert(alertElement);
            bsAlert.close();
        }, 10000); // 10,000 milliseconds = 10 seconds
    });
});