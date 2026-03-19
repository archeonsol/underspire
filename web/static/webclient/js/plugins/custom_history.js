// custom_history.js
console.log("[History] Loading Premium Command Buffer...");

// The Patient Hunter: Wait until GoldenLayout is finished
var historyCheck = setInterval(function() {
    var inputField = document.getElementById("inputfield");
    
    // Check if the field exists AND if Evennia's plugin handler is fully booted
    if (inputField && window.plugin_handler && !inputField.dataset.historyBound) {
        clearInterval(historyCheck); // Stop checking!
        
        // Mark it so we never accidentally attach twice
        inputField.dataset.historyBound = "true"; 
        console.log("[History] GoldenLayout UI loaded. Hijacking text box!");

        var cmdHistory = JSON.parse(localStorage.getItem("mud_cmd_history") || "[]");
        var historyIndex = cmdHistory.length;
        var currentDraft = ""; 

        // THE CAPTURE PHASE: Notice the "true" at the very end of this function.
        // It guarantees our script gets the keystrokes before Evennia's core scripts do.
        inputField.addEventListener("keydown", function(e) {
            
            // 1. Handle ENTER
            if (e.key === "Enter" && !e.shiftKey) {
                var val = inputField.value.trim();
                if (val) {
                    if (cmdHistory.length === 0 || cmdHistory[cmdHistory.length - 1] !== val) {
                        cmdHistory.push(val);
                        if (cmdHistory.length > 50) cmdHistory.shift();
                        localStorage.setItem("mud_cmd_history", JSON.stringify(cmdHistory));
                    }
                }
                historyIndex = cmdHistory.length;
                currentDraft = "";
            }
            
            // 2. Handle UP ARROW
            else if (e.key === "ArrowUp") {
                if (cmdHistory.length > 0) {
                    e.preventDefault(); 
                    e.stopPropagation(); // BLOCKS Evennia from stealing the keystroke
                    
                    if (historyIndex === cmdHistory.length) {
                        currentDraft = inputField.value;
                    }
                    if (historyIndex > 0) {
                        historyIndex--;
                        inputField.value = cmdHistory[historyIndex];
                    }
                }
            }
            
            // 3. Handle DOWN ARROW
            else if (e.key === "ArrowDown") {
                if (cmdHistory.length > 0) {
                    e.preventDefault();
                    e.stopPropagation(); // BLOCKS Evennia from stealing the keystroke
                    
                    if (historyIndex < cmdHistory.length - 1) {
                        historyIndex++;
                        inputField.value = cmdHistory[historyIndex];
                    } else if (historyIndex === cmdHistory.length - 1) {
                        historyIndex++;
                        inputField.value = currentDraft;
                    }
                }
            }
        }, true); // <-- THIS 'true' IS THE MAGIC KEY
        
        console.log("[History] Buffer active. Loaded " + cmdHistory.length + " previous commands.");
    }
}, 200); // Check every 200ms