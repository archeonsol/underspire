// mygame/web/static/webclient/js/history.js

(function() {
    let commandHistory = [];
    let historyPointer = -1;
    let currentInputSaved = "";

    // Wait for the document to be ready
    window.addEventListener("DOMContentLoaded", function() {
        // Find the Evennia input set (standard ID is #messagetext)
        const inputField = document.querySelector("#messagetext");
        
        if (!inputField) return;

        inputField.addEventListener("keydown", function(event) {
            if (event.key === 'Enter') {
                const val = inputField.value.trim();
                if (val) {
                    commandHistory.push(val);
                    // Limit history to 50 items so it doesn't eat memory
                    if (commandHistory.length > 50) commandHistory.shift();
                    historyPointer = commandHistory.length;
                }
            } 
            
            else if (event.key === 'ArrowUp') {
                if (historyPointer > 0) {
                    if (historyPointer === commandHistory.length) {
                        currentInputSaved = inputField.value;
                    }
                    event.preventDefault(); 
                    historyPointer--;
                    inputField.value = commandHistory[historyPointer];
                }
            } 
            
            else if (event.key === 'ArrowDown') {
                if (historyPointer < commandHistory.length) {
                    event.preventDefault();
                    historyPointer++;
                    if (historyPointer === commandHistory.length) {
                        inputField.value = currentInputSaved;
                    } else {
                        inputField.value = commandHistory[historyPointer];
                    }
                }
            }
        });
    });
})();