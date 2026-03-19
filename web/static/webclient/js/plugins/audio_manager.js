// audio_manager.js
// Native Evennia Webclient Plugin for handling audio OOB messages.

var audio_plugin = (function () {
    var currentTrack = null;

    // This function will automatically fire when Evennia sends caller.msg(play_music="...")
    var onPlayMusic = function (args, kwargs) {
        var url = args[0]; // Evennia wraps the argument in an array
        console.log("[Audio Manager] Playing track: " + url);

        if (currentTrack) {
            currentTrack.pause();
            currentTrack.currentTime = 0;
        }

        currentTrack = new Audio(url);
        currentTrack.volume = 0.4;
        currentTrack.loop = true;

        currentTrack.play().catch(function(err) {
            console.warn("[Audio Manager] Autoplay blocked by browser. User must interact first.", err);
        });
    };

    // This function will automatically fire when Evennia sends caller.msg(stop_music=True)
    var onStopMusic = function (args, kwargs) {
        console.log("[Audio Manager] Fading music out.");
        if (currentTrack) {
            var fadeAudio = setInterval(function () {
                if (currentTrack.volume > 0.05) {
                    currentTrack.volume -= 0.05;
                } else {
                    currentTrack.pause();
                    clearInterval(fadeAudio);
                }
            }, 200);
        }
    };

    var dispatchUnknown = function (cmdname, args, kwargs) {
        if (cmdname === "play_music") {
            onPlayMusic(args || [], kwargs || {});
            return true;
        }
        if (cmdname === "stop_music") {
            onStopMusic(args || [], kwargs || {});
            return true;
        }
        return false;
    };

    // We return an object that tells Evennia which hooks this plugin handles
    return {
        init: function () {
            console.log("[Audio Manager] Plugin registered successfully.");
        },
        // Some Evennia versions surface custom output events as unknown commands.
        // Handle those here so caller.msg(play_music="...") is routed correctly.
        onUnknownCmd: dispatchUnknown,
        // Keep direct keys too, for compatibility with setups that support them.
        play_music: onPlayMusic,
        stop_music: onStopMusic
    };
})();

// Add our new plugin to Evennia's official router
window.plugin_handler.add("audio_manager", audio_plugin);