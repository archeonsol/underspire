"""
Cybersurgery narratives: per-implant install and removal message sequences.

Each entry is a list of strings shown to the surgeon at timed intervals during
the procedure. Second-person present tense. Grimdark arcanepunk.

Install narratives have 4 steps (standard) or 6 steps (limb/major).
Removal narratives have 4 steps.

Keys match the surgery_narrative_key on each CyberwareBase subclass.
If a cyberware object has no surgery_narrative_key, fall back to
"generic_implant" / "generic_removal".
"""

CYBERWARE_INSTALL_NARRATIVES = {
    "generic_implant": [
        "You cut. The skin parts and the fat layer beneath it weeps yellow. You retract, clamp, and mop the field. The implant sits on the tray beside you, cold and patient. It has been waiting for this longer than the patient has.",
        "You clear the tissue bed. Muscle fiber and fascia peel back under your blade. The body does not want this - every layer resists, every vessel bleeds in protest. You cauterize what you must and sacrifice what you must. The interface site is raw and glistening.",
        "The implant goes in. Metal meets meat. You seat it, align it, test the contact points. The bonding agent hisses where it touches living tissue. The table shudders under involuntary spasms. You pin the site closed-handed until the interface sets.",
        "You close. Layer by layer, the body swallows what you have put inside it. The sutures pull the skin over chrome like a lie over the truth. You dress the site, strip your gloves, and step back. The body will decide whether to accept this or reject it. You have done your part.",
    ],
    "chrome_arm": [
        "You mark the line. Mid-humerus or higher - wherever the damage ends and viable tissue begins. The tourniquet goes on. You cut through skin, then fat, then muscle. The saw bites bone with a sound that fills the theatre. Blood sprays the drape. The limb comes away in your hands - heavier than you expect. It always is. You set it aside. The stump bleeds.",
        "You prepare the interface. The bone is filed flat, the marrow canal reamed and fitted with the anchor sleeve. You seat it with a mallet - controlled strikes, precise angle. The sound is wet and solid. Then the vascular manifold: you splice the brachial artery to the chrome feed line, prime it, and watch dark blood fill the channels. No leak. The stump is a ruin of exposed anatomy and surgical steel.",
        "You connect the nerves. Each trunk is isolated, stripped, and mated to its chrome counterpart. Motor. Sensory. Proprioception. You work under magnification with instruments that cost more than the patient is worth. One wrong splice and the arm will move when they think about breathing. You do not make that mistake. Not today.",
        "The arm seats into the interface with a sound like a bolt being thrown. You lock it, torque it, test the range. The chrome fingers open and close. The wrist rotates. The shoulder joint articulates. It is not graceful. It is functional. The body's nervous system is screaming at the intrusion. You can see it in the vitals. You do not care.",
        "You connect the dermal junction - where chrome meets skin. This is the seam that will define the rest of their life. You suture synthetic membrane to biological tissue, layer by layer, sealing the interface against infection and the world. The scar will be ugly. Everything about this is ugly.",
        "You close the last layer and dress the site. The arm hangs at their side, chrome and cable and hydraulic muscle. It does not match the other arm. It never will. You strip your gloves and drop them in the biohazard bin. The autoclave hums. Another body rebuilt. Another piece of someone replaced with something that will outlast them.",
    ],
    "chrome_leg": [
        "You mark the disarticulation line at the hip or the amputation line at the femur - wherever the wreckage ends. The tourniquet bites into the groin. You cut. Skin, fat, the thick ropes of thigh muscle, the femoral bundle that could kill them in minutes if you nick it. The saw takes the bone. The leg separates. You bag it and set it aside. The stump pumps. You clamp.",
        "The interface socket goes in. You ream the femoral canal - or the acetabulum if it is a full hip disarticulation - and hammer the anchor home. The bone protests. You reinforce with screws. Then the vascular work: femoral artery to chrome feed, femoral vein to chrome return. You prime the circuit. Blood flows through metal tubing. The leg is not attached yet but its plumbing is alive.",
        "You expose the sciatic nerve trunk - the biggest nerve in the body, thick as your finger. You split it into its component bundles and mate each one to the chrome interface array. Tibial. Peroneal. The small cutaneous branches that will let them feel the ground beneath a foot that is not theirs. You solder, seal, and test. The nerve monitor shows signal. The leg will know where it is in space.",
        "The leg seats with a pneumatic thud that you feel through the table. You lock the interface, torque the bolts, run the full range: flex, extend, rotate, abduct. The chrome knee bends. The ankle articulates. The foot grips. The patient's brain is sending commands to a machine and the machine is obeying. It works. It always feels like violence when it works.",
        "You close the junction site. Synthetic skin over chrome over bone. The seam runs around the thigh like a belt - ragged, red, held together with sutures and surgical adhesive and the hope that the tissue will accept what has been done to it. You irrigate, you drain, you dress.",
        "You step back. The leg is chrome from hip to toes. It will carry them, run for them, kick for them. It will outlast every other part of their body. The theatre smells like cautery and blood and the ozone of surgical tools. You peel off your gloves. Your hands ache. Another one done.",
    ],
    "chrome_hand": [
        "You tourniquet the forearm. The hand has to come off at the wrist - a disarticulation, not a cut. You sever the ligaments, the tendons, the radial and ulnar arteries. The hand separates from the arm like a glove being removed, except for the blood. You bag it. The stump is a cross-section of human anatomy, open and weeping.",
        "You prepare the interface. The radius and ulna get anchor sleeves. The tendons are tagged and mapped - each one will mate to a servo actuator in the chrome hand. You splice the arteries to the vascular ports and prime the circuit. Blood moves through channels that were machined, not grown.",
        "The chrome hand seats onto the wrist interface. You lock it. Then the delicate work: each tendon mated to its actuator, each nerve bundle - median, ulnar, radial - soldered to its chrome counterpart. The fingers will move. They will grip. They will feel pressure and temperature, but not texture. Not the way a real hand feels things. That is gone.",
        "You close the junction. The seam around the wrist is tight, surgical, angry red. You test the hand: open, close, pinch, grip, point. Each finger responds. The thumb opposes. It is a hand. It will do what hands do. You dress the site and step back. They will learn to live with the cold of it. Everyone does.",
    ],
    "chrome_eyes": [
        "You retract the lids with speculums. The biological eyes stare up at you - the last things they will see with the equipment they were born with. You sever the extraocular muscles one by one. The eye rotates freely, untethered. You clamp the optic nerve and cut. The globe comes out in your hand, trailing fluid. You do it twice.",
        "The sockets are raw, red, empty. You irrigate and inspect - the orbital walls are intact. You seat the chrome housings: machined titanium cups that will hold the new optics. Screws into bone. The drill whines. You fit the vascular ports to the ophthalmic arteries - the new eyes need blood supply for the interface tissue that lines the socket.",
        "The chrome eyes go in. They click into their housings like rounds into a chamber. You connect the optic nerve interfaces - twelve thousand fibers per eye, bundled and mated to a chip the size of a grain of rice. The calibration sequence runs: the apertures open, contract, focus. The lenses track your finger. They see. What they see and how they see it is no longer in the body's hands.",
        "You close. The lids go back over chrome instead of cornea. The fit is tight and swollen. You suture the canthi, dress the orbits, apply antibiotic gel. When they open their eyes, the world will be sharper, colder, and hostile in wavelengths flesh never handled.",
    ],
    "chrome_eye_single": [
        "You retract the lid. The eye tracks your hand until you sever the muscles, clamp the nerve, and extract the globe. It comes out wet and whole. One socket empty, one still occupied. The asymmetry is immediate and grotesque.",
        "You seat the chrome housing. Screws into the orbital rim. The drill bites bone and the patient's jaw clenches even under sedation. You fit the vascular port to the ophthalmic artery on that side - the new eye needs blood flow for the interface membrane.",
        "The chrome eye clicks in. You mate the optic nerve interface: six thousand fibers on this side, each one carrying a signal that the brain will learn to interpret as sight. The lens focuses. The aperture adjusts. One eye chrome, one eye meat. The brain will reconcile the difference or it will not.",
        "You close the lid over the implant and suture the canthus. The chrome eye sits beside its biological twin with a hard mismatch in focus and latency. You dress the site. The patient wakes to split feeds and conflicting depth, then relearns sight by force.",
    ],
    "audio_implant": [
        "You make the incision behind the ear. Small, precise - the mastoid bone is right there. You drill a channel through bone into the cochlear region. The sound it makes is intimate and terrible: a dentist's drill inside someone's skull. Blood and bone dust mix into pink paste.",
        "You seat the receiver array against the cochlear nerve bundle. The wire is thinner than a hair and carries more signal than the biological cochlea ever did. You bond it to the nerve with conductive adhesive and pray to whatever machine-spirit governs this work that the signal finds its way.",
        "You test the circuit. A tone generator pressed to the receiver - the patient flinches. The nerve heard it. You calibrate: low frequencies, high frequencies, the range of human speech and beyond. The implant will hear things the ear was never designed to catch. Subvocal. Ultrasonic. The quiet sounds that people think no one hears.",
        "You close the incision. The chrome strip sits behind the ear, flush with the skin. You secure it with tissue adhesive. The scar is a thin line in the hairline. The patient will hear everything, including blood flow, tendon friction, and breath behind walls.",
    ],
    "olfactory_booster": [
        "You go in through the nostrils. No external incision - the work is endoscopic, guided by a scope the width of a pen. You navigate the nasal cavity until you reach the olfactory epithelium, that thin layer of cells where smell becomes thought. The tissue is delicate. You handle it like wet paper.",
        "You lay the chrome mesh over the epithelium. Microscopic sensors, each one calibrated to a molecular receptor class. The mesh bonds to the mucosa with biological adhesive - it will integrate with the living tissue over days, becoming part of the nasal lining. The body will try to reject it. The adhesive is designed to win that argument.",
        "You connect the signal wire to the olfactory bulb interface - a chip seated just above the cribriform plate, inside the skull. This is the dangerous part. One millimeter wrong and you are in the brain. You are not in the brain. You seat the chip and test the circuit. A swab of alcohol held under the nose: the readout spikes. It works.",
        "You withdraw the scope and pack the nostrils. No sutures - the tissue will heal around the mesh. The patient will sneeze blood for two days. Then they will smell things they never knew existed. Every chemical. Every pheromone. Every lie someone's body tells before their mouth opens.",
    ],
    "subdermal_plating": [
        "You open the torso with a long midline incision. Then the flanks. Then the back - they have to be repositioned twice. The skin flaps hang like curtains, exposing the fascial layer beneath. You have mapped the plating geometry in advance. Fifty-six hexagonal plates, each one cut to fit the body's contours. They go in one at a time.",
        "You seat each plate against the fascia and anchor it with biocompatible screws. The tissue beneath compresses, adapts, protests. The plates overlap at the edges like scale armor - the body becomes a thing with a shell. You work for what feels like hours because it is hours. Blood loss is steady and managed. The patient's vitals drift but hold.",
        "You test the coverage: press, strike, probe. The plates distribute force across their surface. A knife would skid. A bullet would flatten. The body beneath still bruises, still breaks - but the threshold for damage has shifted upward. The price is sensation. The nerve endings beneath the plates are crushed, cauterized, dead. They will never feel gentle touch on these surfaces again.",
        "You close the skin over the plating. The incisions are long and the sutures are many. Beneath the surface, the body is armored. Above it, the skin sits over chrome like upholstery over steel. The geometric lines will be visible when the swelling goes down - faint, subcutaneous, permanent. You dress the wounds and let the table do the rest.",
    ],
    "dermal_weave": [
        "You make a series of small incisions - twelve in total across the torso and abdomen. Through each one, you feed the weave: a carbon-fiber mesh thinner than paper and stronger than the skin it will reinforce. The tool that places it looks like a crochet hook designed by a weapons manufacturer. You work it between the dermis and the subcutaneous fat, spreading the mesh beneath the skin like a net beneath a circus.",
        "The mesh unfurls as you place it. Each section bonds to the one beside it, forming a continuous layer that follows the body's contours. The adhesive activates on contact with body heat. You can feel it tighten through the tissue - the skin draws taut over the weave, reshaping itself around the new substrate. The body is being lined with something that was not born in it.",
        "You test the integration: pinch the skin and it snaps back faster than biology allows. Press a blade tip and the weave catches it before the dermis parts. It is not armor - it is reinforcement. The difference between a wall and a wall with rebar. The skin looks normal. Almost. The texture is slightly wrong, the elasticity slightly too perfect.",
        "You close the twelve incisions. Small sutures, minimal scarring. The weave is invisible except to touch and to the knowing eye. The patient will move normally, look normal, feel almost normal. But when something tries to cut them, it will have to cut through engineering first.",
    ],
    "bone_lacing": [
        "You open the body in stages. The long bones first: femur, humerus, tibia, radius, ulna. Each one requires its own incision, its own exposure. You strip the periosteum - the thin membrane that wraps the bone - and expose the cortex beneath. White, hard, alive. You are about to coat it in something harder.",
        "The lacing compound is a metalite-calcium composite delivered as a heated gel. You apply it to the bone surface with a pressurized applicator. It bonds on contact, seeping into the cancellous structure, filling the trabecular spaces, hardening as it cools. Each bone takes four to six applications. The ribs. The pelvis. The vertebrae - those are the worst. You work around the spinal cord with the care of someone defusing a bomb.",
        "The skull is last. You drill burr holes - four of them - and inject the compound through each one. It flows along the inner and outer tables of the skull, coating the bone in a shell that will not crack where calcium would. The patient's skeleton is becoming something that will outlast the flesh around it. You can hear the compound settling: a faint ticking as it crystallizes.",
        "You close everything. The incisions are numerous and the body looks like it has been opened by a coroner and reassembled. But beneath every wound, the bones are laced with metal. They will not break easily. They will not break at all unless something truly extraordinary hits them. The price is weight. The patient is heavier now. They will feel it when they stand.",
    ],
    "skin_weave": [
        "You prepare the recipient sites with dermal abrasion - mechanically removing the outer layers of skin in long, even strokes. The raw surface beneath is red, weeping, and ready to accept the overlay. The synthetic skin comes in sheets, custom-cut to the body's measurements. You lay the first sheet and press it flat. The bio-adhesive activates on contact with blood.",
        "Sheet by sheet, you cover the designated areas. The synthetic skin bonds to the dermal bed as if it were always meant to be there. The edges are feathered and blended - invisible at arm's length, detectable only at close inspection. You seal each junction with tissue adhesive. The body beneath is still human. The surface is not.",
        "You test the integration. The synthetic surface responds to temperature, registers pressure, but the resolution is lower than biological skin. Fine touch is muted. Pain is dulled. The tradeoff is a surface that can be anything: any color, any texture, any pattern the owner chooses. The skin is a canvas now. The body is the frame.",
        "You dress the sites with breathable film and let the adhesion cure. The patient peels and flakes for a week as dead epidermis sloughs off in sheets and the synthetic surface locks into place. The final result is durable, numb in patches, and visibly manufactured at close range.",
    ],
    "wired_reflexes": [
        "You open the spine. A long posterior incision from C2 to L1 - the full length of the neural highway. You retract the paraspinal muscles and expose the laminae. The laminotomy is careful: thin cuts to open windows over each spinal segment without destabilizing the column. Through each window, the dura is visible. The spinal cord pulses beneath it.",
        "You lay the filament array along the dura. Chrome threads thinner than spider silk, each one a signal accelerator that will boost nerve conduction velocity by three hundred percent. You bond them to the dural surface at each segment with conductive adhesive. The work takes hours. The magnification makes your eyes ache. One slip and you sever the cord. You do not slip.",
        "You close the laminae, seating each bone window back into its frame and securing it with microplates. The filaments run the length of the spine now, a chrome nervous system laid over the biological one. You extend the array into the neck: a subcutaneous channel carries the filaments to the brainstem relay. The body's reaction time is about to halve. Then halve again.",
        "You close the incision. It runs the full length of the back - a seam that will scar into a rope of tissue. Beneath it, the body's nervous system has been upgraded. Signals that took twelve milliseconds now take three. The brain will need to learn to keep up with itself. Some patients describe it as living in fast-forward. Others describe it as the world slowing down. You dress the wound and let the chrome teach the body what speed means.",
    ],
    "synaptic_accelerator": [
        "You shave the area behind the left ear and mark the incision line. The cut goes through skin and temporalis muscle to expose the skull. The burr hole is precise - twenty millimeters, no more. Through it, you can see the dura pulsing with arterial pressure. Beneath that membrane is the temporal lobe. You are about to put a machine next to it.",
        "You open the dura with a cruciate incision and retract the flaps. The brain is there. Grey, wet, alive, and more fragile than anything else in the room. You seat the accelerator chip against the temporal cortex - a wafer of chrome and silicon the size of a fingernail that processes information faster than the tissue it is touching. The contact electrodes sink into the cortical surface. The brain does not flinch. It has no pain receptors. It does not know what you are doing to it.",
        "You connect the external port. A cable from the chip to a subcutaneous socket behind the ear, where a chrome disc will sit flush with the skin. The port allows future calibration and data exchange. You seal the dura, replace the bone plug, and secure it with a titanium plate. The brain is closed again. It is no longer alone in there.",
        "You close the skin over the port. The chrome disc is visible behind the ear - small, smooth, permanent. The patient will think faster, process more, remember better. The cost is that the chip runs hot when it works hard, and when it fails, it fails inside the skull. You dress the wound and step away from the most dangerous square inch of surgery you will do this week.",
    ],
    "pain_editor": [
        "You make a small incision at the base of the skull, just above the C1 vertebra. The suboccipital muscles part. Beneath them, the foramen magnum - the hole where the brain becomes the spine. You do not go through it. You go beside it, into the space where the dorsal columns carry pain signals upward. You are about to put a gate on that road.",
        "The pain editor is a disc the size of a large coin. You seat it against the dorsal column surface and secure it with conductive clips. The disc intercepts ascending pain signals and filters them - not blocking, not eliminating, but editing. The signal reaches the brain but the brain no longer interprets it as urgent. The body will still be damaged. The mind will no longer care.",
        "You calibrate the filter. A pinch test on the hand: the patient registers pressure but not pain. A needle: they feel the prick but do not withdraw. The reflex is gone. The information is still there but it has been stripped of its emotional weight. You adjust the gain until the patient can feel enough to function but not enough to suffer. The line between those two things is thinner than you would like.",
        "You close the incision. The scar is small, hidden in the hairline. Nociception is now filtered at the column. They will fight without flinching, tear tissue without withdrawal, and bleed through damage they can still see but no longer feel as urgent.",
    ],
    "threat_assessment": [
        "You make bilateral incisions at the temples. Through each one, you drill a burr hole and expose the dura over the parietal lobe - the region where the brain builds its model of the surrounding space. You are about to give it better data.",
        "The threat assessment array is two chips, one per hemisphere, connected by a subcutaneous bridge cable that crosses the crown of the skull beneath the scalp. You seat each chip against the parietal cortex. The electrodes sink into grey matter. The chips begin sampling: spatial data, movement vectors, threat prioritization. The brain did this already. The chips do it faster and without emotional bias.",
        "You connect the array to the optic nerve tap - this requires a chrome eye to function. The visual feed routes through the assessment module before reaching conscious awareness. The result is a combat overlay: targets highlighted, trajectories predicted, openings identified. The patient will see the world annotated. The annotations will save their life or drive them mad. Sometimes both.",
        "You close the incisions and secure the bridge cable beneath the scalp. The scars will trace the temples and cross the crown. The patient will process combat information before conscious thought can interfere. The downside is that in a crowd, every person becomes a potential threat vector. The module does not turn off. It does not know how to stop evaluating.",
    ],
    "memory_core": [
        "You make the incision at the left temple. Through the burr hole, you expose the temporal lobe - the seat of memory, the archive of a life. You are about to give it an annex. The memory core is a cylinder the size of a AA battery, sheathed in biocompatible chrome. It goes into a pocket you carve in the temporal bone, pressed against the cortex.",
        "You connect the electrode array. Forty-eight contacts, each one touching a different region of the hippocampal formation and the surrounding cortex. The core will record, index, and retrieve. Perfect recall - not the fuzzy, emotional, reconstructed memory that biology provides, but machine-precise playback. Every word. Every face. Every detail the eyes saw and the brain forgot.",
        "You test the interface. You hold up a card with a number sequence. The patient reads it. You take the card away. The core's indicator light pulses once - recorded. You ask them to recall. They do, instantly, accurately, without the usual pause of biological retrieval. The memory is there. It will always be there. The core does not forget. It does not prioritize. It does not spare them the things they would rather not remember.",
        "You close the incision. The core sits in its bone pocket, ticking faintly with each write cycle. The patient will carry every moment with perfect clarity. The gift is knowledge. The curse is that they cannot choose to forget.",
    ],
    "cardiopulmonary_booster": [
        "You open the chest. Median sternotomy - the saw splits the breastbone and you crank the retractor until the ribs part like a cage being opened. The heart is there, beating. The lungs inflate and deflate on either side. You are looking at the engine room. You are about to bolt an afterburner to it.",
        "The booster housing seats against the pericardium - the membrane that wraps the heart. You suture it in place, then connect the arterial tap: a chrome shunt that samples blood flow, oxygenation, and pressure in real time. The booster's own pump supplements the heart's output. Two pumps now. The mechanical one never tires, never fibrillates, never slows unless the power fails.",
        "You connect the pulmonary interface: a mesh that wraps the bronchial tree and supplements gas exchange. The lungs become more efficient - more oxygen per breath, faster CO2 clearance. The patient will breathe like a machine. Steady. Deep. Relentless. The body will push harder and longer than any unaugmented frame should. The heart will pay for it eventually. Everything pays eventually.",
        "You close the sternum with wire. The retractor comes out. The ribs spring back. Inside the chest, the booster clicks - one beat behind the heart, then in sync, then ahead. The patient's physiology has been overclocked. You dress the sternal wound and step back. The clicking will never stop. It will be the last thing they hear when they sleep and the first thing they hear when they wake.",
    ],
    "adrenal_pump": [
        "You open the abdomen with a subcostal incision on the left. Through the peritoneum, you navigate past bowel and omentum until you find the adrenal gland - small, yellow, sitting atop the kidney like a cap. You are about to turn this gland into a weapon.",
        "The pump housing clamps around the adrenal gland without removing it. Chrome fingers grip living tissue. You connect the reservoir - a pressurized capsule of synthetic adrenaline and norepinephrine, enough for three combat surges before it needs to regenerate from the gland's own output. The feed line splices into the renal vein. Chemical warfare, internal.",
        "You calibrate the trigger. A subcutaneous pressure switch in the abdomen - the patient clenches a specific muscle group and the pump fires. The synthetic cocktail hits the bloodstream like a freight train. Heart rate spikes. Pupils blow. Pain signals flatten. For thirty seconds, the patient is faster and stronger than any human has a right to be. After that, the crash comes. The crash always comes.",
        "You close the abdomen. The pump sits inside them, pressurized and waiting. A weapon loaded and chambered inside the body. You dress the wound and make a note in whatever record you keep. The patient has been given a button that trades tomorrow's function for today's survival. How often they press it is not your problem.",
    ],
    "toxin_filter": [
        "You open the flank with a lateral incision. Through the retroperitoneal space, you find the renal hilum - the junction where blood enters and leaves the kidney. You are not here for the kidney. You are here for the blood that passes through it.",
        "The filter housing splices into the renal vasculature: arterial in, venous out, with the filtration unit sitting in the retroperitoneal fat like a chrome kidney beside the biological one. You prime the circuit. Blood flows through the filter. Inside, molecular sieves and enzymatic catalysts strip toxins, metabolize drugs, and neutralize poisons before the blood returns to circulation.",
        "You test the filter. A controlled micro-dose of ethanol into the IV line. The blood alcohol level spikes, then drops - faster than any liver should manage. The filter is working. Poisons will find less purchase. Drugs will burn shorter. The body's chemistry is being managed by a machine now. For better and worse.",
        "You close the flank. The filter hums in its cavity, processing every drop of blood that passes through the renal circuit. The patient will metabolize faster than nature intended. Alcohol, narcotics, medication, and poison - all processed with mechanical efficiency. The filter does not distinguish between what they want in their blood and what they do not. It cleans everything.",
    ],
    "metabolic_regulator": [
        "You make a small abdominal incision and navigate to the vagus nerve trunk where it passes through the diaphragm. The vagus controls hunger, satiety, heart rate, digestion - the body's autopilot. You are about to replace the autopilot with something that flies straighter.",
        "The regulator clips onto the vagus nerve like a parasite. Chrome arms grip the nerve trunk and interdigitate with the signal fibers. It will read the body's metabolic state in real time and override what it does not like. Hunger? Suppressed until fuel is needed. Thirst? Regulated to optimal hydration. Sleep? Scheduled, not negotiated with.",
        "You test the interface. The regulator pulses and the patient's heart rate settles to a metronomic sixty. The gut goes quiet - not the silence of death but the silence of control. The body has been put on a leash. It will eat when told, drink when told, and rest when told. The freedom of appetite is gone. The efficiency of machinery takes its place.",
        "You close the incision. The regulator is small enough to disappear in the abdominal fat. Its control path runs the length of the vagus nerve, from brainstem to bowel. Appetite, thirst, and rest are now algorithmic outputs instead of urges.",
    ],
    "hemostatic_regulator": [
        "You make a small incision over the subclavian vein on the left. Through the vessel wall, you thread the regulator catheter into the central venous system - it will sit at the junction of the vena cava and the right atrium, sampling every drop of blood that returns to the heart.",
        "The regulator housing seats against the vessel wall and anchors with self-expanding barbs. Inside, it monitors coagulation factors in real time and releases synthetic clotting accelerants when it detects bleeding. The response time is faster than the body's own cascade. Wounds that would bleed for minutes will seal in seconds. The clots are dark, uniform, and mechanical - nothing like the body's own messy fibrin webs.",
        "You test the unit. A small lancet cut on the patient's forearm: blood wells, then stops. Three seconds. The natural cascade takes fifteen to thirty. The regulator earned its keep in a single demonstration. But the machine does not know when to stop clotting. In the wrong circumstances, it will seal vessels that should stay open. Thrombosis. Stroke. Pulmonary embolism. The risks are real.",
        "You close the incision over the subclavian. The regulator sits in the central circulation, ticking, counting platelets, and waiting for the next wound. The patient will bleed less. They will also carry a machine that makes blood clots for a living sitting next to their heart. You dress the wound and do not think about what happens when the machine gets it wrong.",
    ],
    "voice_modulator": [
        "You make a transverse incision across the anterior neck, just above the thyroid cartilage. You dissect through the strap muscles and expose the larynx - the voice box. It is a small, delicate structure that produces every sound the patient has ever made. You are about to wrap it in chrome.",
        "The modulator is a thin chrome band studded with piezoelectric elements. You seat it around the larynx, over the thyroid cartilage, and secure it with micro-sutures to the surrounding tissue. The elements will read and modify the vibrations of the vocal cords in real time - pitch, timbre, resonance, projection. The voice becomes an instrument with a chrome bow.",
        "You connect the control wire to a subcutaneous switch at the base of the throat. The patient will learn to modulate by subtle muscle movements - a language of the neck that no one else will see. You test the device: the patient vocalizes and the sound that comes out is richer, fuller, more controlled than any biological voice. It is also no longer entirely theirs.",
        "You close the neck. The chrome band is invisible from the outside - buried beneath muscle and skin, wrapped around the seat of speech. The scar will be a thin line across the throat. The voice that emerges will be a collaboration between meat and machine. In the right hands, it will persuade, perform, command. In the wrong hands, it will deceive. You dress the wound and do not ask which it will be.",
    ],
    "grip_pads": [
        "You make small incisions in each palm and along each fingertip - ten cuts in total, precise and shallow. Through each one, you insert a pad of synthetic grip material: micro-hooked fibers bonded to a polymer substrate. They go beneath the skin of the palms and fingertips, replacing the subdermal fat layer with something that grips.",
        "You bond each pad to the underlying fascia with surgical adhesive. The pads are thin - barely a millimeter - but the grip surface is engineered at the molecular level. Van der Waals forces, mechanical interlocking, controlled friction. The hands will hold what they hold. Weapons will not slip. Tools will not turn. Surfaces that would defeat bare skin will yield.",
        "You test the grip. The patient closes their hand around a steel rod. You pull. The rod does not move. The grip is not strength - the muscles are the same. It is adhesion. The hands have become surfaces that do not let go until the brain says otherwise. The fine motor cost is minimal: the pads are thin enough to preserve most dexterity. Most.",
        "You close the incisions. Twenty sutures, ten fingers, two palms. The scars will fade into the creases of the hand and the whorls of the fingertips. No one will see the chrome. They will only feel it when they shake the patient's hand and notice that the grip is too even, too controlled, too deliberate to be entirely natural.",
    ],
    "targeting_reticle": [
        "The patient already has chrome eyes. Good. Without them, this implant is a paperweight. You make an incision at the temple - right side - and expose the lateral aspect of the chrome eye housing. There is a data port built into the housing for exactly this purpose. The eye was designed to accept accessories. The eye was designed to accept this.",
        "The targeting module is a chip the size of a sesame seed. You seat it into the data port and lock it. A firmware handshake runs: the chip introduces itself to the optic processor and requests access to the visual feed. Access granted. The chip will overlay targeting data onto the patient's visual field - range estimation, trajectory calculation, windage compensation, target lead. The eye becomes a weapon sight.",
        "You calibrate the reticle. The patient focuses on a target across the room. The chip calculates distance, estimates time-to-impact for a standard projectile, and projects a subtle amber overlay onto the visual field. The patient nods. They can see it. A ghost of geometry hanging in their vision, pointing at where the bullet should go.",
        "You close the temple incision. The chip is invisible, buried in the eye housing. Its presence is betrayed only by the occasional amber flicker across the chrome lens - a ghost of math made visible. The patient's aim will improve. Their shooting will become mechanical, calculated, cold. The difference between a marksman and a machine is now a matter of degree.",
    ],
    "subvocal_comm": [
        "You make a small incision over the larynx. Through it, you expose the thyroarytenoid muscles - the muscles that move the vocal cords. You are not here to modify the voice. You are here to listen to it before it becomes sound.",
        "The subvocal sensor is a thin chrome strip that you lay across the laryngeal muscles. It reads the micro-contractions that precede speech - the shadow of a word, formed in the muscles but not yet released as sound. The sensor captures this shadow, encodes it, and transmits it. The patient will learn to speak without speaking. Lips move. No sound comes out. The message goes somewhere else.",
        "You connect the transmission wire to a subcutaneous antenna in the neck. The signal is short-range - local Matrix network only. Encrypted by default, interceptable by design if someone knows what to look for. You test the device: the patient mouths a word. The receiver across the room registers it. Communication without sound. Conspiracy made convenient.",
        "You close the incision. The sensor strip is invisible, the antenna buried. The patient will move their mouth while transmitting silence over short-range channels. To observers it reads as muttering with no sound and no breath pattern to match speech.",
    ],
    "adrenaline_shunt": [
        "You open the abdomen with a small subcostal incision. Through it, you navigate to the adrenal gland - the same approach as the pump, but the shunt is simpler. No reservoir, no trigger mechanism. Just a regulator that sits between the gland and the bloodstream.",
        "The shunt clips onto the adrenal vein with chrome jaws. Inside, a molecular filter meters the adrenaline output - smoothing the spikes, extending the plateaus, eliminating the crashes. The body's fight-or-flight response becomes a managed resource instead of a panic button. Steady, controlled, cold. The heart does not race. The hands do not shake. Fear is replaced by assessment.",
        "You test the shunt. A sudden loud noise near the patient: the startle response is absent. The heart rate increases by four beats per minute instead of forty. The pupils dilate one millimeter instead of three. The body is ready for threat without the biological hysteria that usually accompanies readiness. It is efficient. It is also deeply unsettling to witness.",
        "You close the incision. The shunt sits on the adrenal gland, regulating the oldest chemical response in the human body. The patient will be calm under fire, steady under pressure, unmoved by surprise. Other people will notice. The absence of normal stress responses reads as cold, mechanical, wrong. The patient will be effective. They will also be alone in a way that adrenaline-having people cannot understand.",
    ],
    "retractable_claws": [
        "You make incisions along each finger, dorsal side. Through each one, you expose the distal phalanx - the last bone of the finger, the one that holds the nail. You remove the nailbed. All ten of them. The keratin is replaced with chrome housings: sheaths that contain retractable blades, each one honed to a molecular edge. The blades nest beneath the fingertip when retracted. When extended, they are three inches of chrome that will open anything they touch.",
        "You seat the extension mechanism in each finger. A spring-loaded system activated by specific tendon tension - the patient clenches their hand a certain way and the blades deploy. A different tension retracts them. You calibrate each finger independently. The mechanism must be smooth, fast, and silent. A click of deployment is acceptable. A jam is not.",
        "You connect the housings to reinforced tendon anchors. The existing flexor tendons are spliced with synthetic cable - they have to handle both normal grip and blade deployment without tangling. The work is fiddly and unforgiving. Each finger is a separate machine. Each machine must work in concert with nine others.",
        "You close the incisions. The fingers look almost normal - slightly bulkier at the tips, the nailbeds a shade too smooth, but nothing that screams weapon to the casual eye. Beneath the skin, each fingertip holds a blade that would make a surgeon's scalpel feel inadequate. The patient has been given ten knives that they carry inside their own hands. You dress the wounds and do not ask what they intend to cut.",
    ],
}

CYBERWARE_REMOVAL_NARRATIVES = {
    "generic_removal": [
        "You open the old scar. The tissue has grown into the implant - adhesions, scar bands, the body's attempt to make the foreign thing its own. You cut it free. The work is slower than installation. The body does not want to let go of what it has learned to live with.",
        "You disconnect the interface points. Power down, then sever each contact. The implant goes dark. The body does not yet know it is gone. It will. The absence will register as a phantom - a signal expected and not received, a capacity that was there and is not.",
        "You extract the hardware. It comes out trailing filaments of tissue - biological material that grew into chrome crevices and bonded there. The cavity it leaves is raw, bleeding, and shaped like something that no longer exists. You pack it. You irrigate. You check for damage to the surrounding structures.",
        "You close the wound. Where chrome was, there is now a void the body will fill with scar tissue and memory. The implant sits on the tray, wet and organic and mechanical all at once. You dress the site and strip your gloves. Something has been removed. Something else remains - the shape of its absence.",
    ],
    "chrome_arm_removal": [
        "You detach the dermal junction first. The seam where chrome meets skin has matured into a tight, complex boundary of scar tissue and synthetic membrane. You cut through it with care. The chrome arm goes loose at the interface. The patient's biological systems are about to lose a limb for the second time.",
        "You disconnect the neural interface. Each nerve bundle is de-mated from its chrome counterpart - motor, sensory, proprioception. As each one separates, the arm loses a function. The fingers stop responding. The wrist locks. The elbow freezes. The arm dies in stages. The patient feels it go, even under sedation - phantom signals from a connection being severed.",
        "You disconnect the vascular manifold. The arterial feed is clamped, the venous return sealed. Blood stops flowing through chrome channels. You unbolt the interface socket from the bone anchor. The arm separates from the body with a sound that is partly mechanical and partly organic - a wet, metallic pop that you feel through the table.",
        "You close the stump. Where the chrome arm was, there is a raw interface site: bone anchor, capped vessels, tagged nerve trunks, and a circumference of traumatized tissue. You fashion a stump closure from available tissue - muscle flaps, skin advancement. The result is a limb that ends where a machine began. You dress the site. The arm sits on the tray, chrome and cable and the faint smell of blood. It will outlast the body it was taken from.",
    ],
    "chrome_leg_removal": [
        "You open the junction site at the hip or mid-thigh. The interface has matured - tissue has grown into every crevice of the chrome socket, bonding with the metal as if trying to claim it. You cut through the biological adhesions. The chrome leg goes slack as the mechanical locks disengage.",
        "You disconnect the nerve bundles. Sciatic, femoral, the smaller cutaneous branches. Each one de-mated from its chrome receptor. The leg loses sensation in a wave from proximal to distal - hip, thigh, knee, calf, foot. The chrome toes stop gripping. The knee unlocks. The leg becomes dead weight.",
        "You sever the vascular connections. The femoral feed and return are clamped and sealed. Blood stops flowing through the chrome circuit. You unbolt the interface from the femoral anchor or the acetabular socket. The leg separates. It is heavier than the patient remembers. Chrome and hydraulics and the accumulated engineering of something built to outlast bone.",
        "You close the stump. The interface site is a raw crater of bone anchor, capped vessels, and traumatized tissue. You fashion what closure you can - the body was not designed to end here, and the surgery reflects that awkwardness. You dress the site. The patient is lighter by the weight of a chrome leg. The phantom will come. It always does - the brain expecting a signal from a limb that no longer sends one.",
    ],
    "chrome_eyes_removal": [
        "You retract the lids and disconnect the chrome eye housings from their orbital anchors. The screws back out of bone with a grinding reluctance. The vascular ports are clamped and disconnected. The optic nerve interfaces - twelve thousand fibers per eye - are de-mated in a sequence that takes twenty minutes of magnified work. Each fiber lets go with a snap that is felt, not heard.",
        "The chrome eyes come out of their sockets with a click. Empty housings. The orbital cavities are raw - chrome-shaped hollows where bone has remodeled around the implants. You irrigate, inspect for tissue damage, and pack the sockets. If replacement eyes are going in, the cavities need to be prepared. If not, the sockets will be fitted with cosmetic shells or left to scar.",
        "You clean the orbital rims of residual bonding agent and scar tissue. The bone is pitted where the screws sat. The optic nerve stumps are capped and tucked. The patient is blind now - or they have whatever was there before the chrome went in. In most cases, that is nothing. The chrome was the replacement. Removing it removes sight.",
        "You close the lids over empty or prosthetic sockets. The face now carries the evidence of what was taken - slightly sunken orbits, the wrong shape beneath the lids. You dress the sites. On the tray, the chrome eyes stare at the ceiling with their mechanical apertures frozen mid-focus. They will not see again. Neither will the patient, unless something new goes in.",
    ],
    "neural_implant_removal": [
        "You reopen the access site - temple, spine, or skull base, depending on the implant. The scar tissue is dense and vascular; the body has reinforced the area around the intrusion. You cut through it. Beneath, the chrome is where you left it - or where someone left it - bonded to neural tissue that has grown to accommodate it.",
        "You disconnect the electrode contacts. Each one has to be peeled from the neural surface without tearing the underlying tissue. This is the dangerous part. The brain does not like things being pulled off it. The nerve does not like being abandoned by the machine it learned to depend on. You work slowly. You work precisely. You work knowing that speed here means damage.",
        "The implant separates from the neural surface. The tissue beneath is indented, vascularized, shaped by months or years of contact with chrome. It will never be quite the same. The pathways that routed through the implant will seek new connections, reroute, adapt. The brain is resilient. It is also permanently altered. The chrome changes what it touches, even after it is gone.",
        "You close the access site. The incision follows the old scar. The patient will experience a period of adjustment - slower thoughts, duller reflexes, impaired recall, whatever the implant was providing that the biology now has to handle alone. You dress the wound. Somewhere in the patient's brain, neurons are firing into connections that no longer exist. The ghost of chrome lingers longer than the chrome itself.",
    ],
    "subdermal_removal": [
        "You reopen the original incision lines - or make new ones where the old scars have faded. The subdermal implant has been in place long enough for the body to build a capsule around it: scar tissue, fibrous adhesions, biological infrastructure that treats the chrome as a permanent resident. You are evicting it.",
        "You dissect the implant free from its tissue bed. The work is tedious - the body does not surrender foreign objects gracefully. Each plate, each section of weave, each layer of mesh has to be cut free individually. The tissue beneath is raw and bleeding where the chrome peels away. It looks like a burn. It feels like a betrayal.",
        "You inspect the tissue bed. Without the implant, the body is softer, more vulnerable, less structured. The skin sags where it was held taut. The fascia is weakened where it was reinforced. The nerves beneath may recover sensation or they may not. The subdermal layer has been altered by its tenancy. It will never quite return to what it was.",
        "You close the incisions. The body has been de-armored, de-reinforced, de-woven. Whatever protection the chrome provided is gone. The skin sits on muscle and fat and bone, as it was born to. The scars will tell the story of what was there. The vulnerability is the body's again to carry.",
    ],
    "internal_implant_removal": [
        "You open the cavity - chest, abdomen, or neck, depending on where the hardware lives. Inside, the implant has settled into its home. Tissue has grown around it, through it, into it. Blood vessels have rerouted to feed the interface. The body accepted this thing. Now you are taking it back.",
        "You disconnect the implant from its biological connections. Feed lines, monitor leads, nerve taps - each one severed and sealed. The implant powers down. The body's systems stutter as they lose the support they have come to rely on. Heart rate fluctuates. Breathing pattern changes. The body is relearning how to run on its own, and it is doing it badly.",
        "You extract the hardware. It leaves a cavity shaped like itself - an absence the body will have to fill with scar tissue and adaptation. You irrigate the space, check for bleeding, and pack it if needed. The biological system that the implant was augmenting is now unaugmented. It will have to remember how to do its job alone.",
        "You close the wound. The implant is on the tray, wet with the fluids of the body that housed it. The patient will feel the loss - not as pain but as diminishment. Stamina that was there is not. Efficiency that was normal is not. The body works, but it works the way it did before the chrome. Which is to say: like a body. Fragile, slow, and mortal.",
    ],
}

# Maps surgery_narrative_key -> (install_narrative_key, removal_narrative_key)
# If a key is not present here, the key itself is attempted in each dict,
# then generic fallbacks are used.
NARRATIVE_KEY_MAP = {
    # Limbs
    "chrome_arm": ("chrome_arm", "chrome_arm_removal"),
    "chrome_leg": ("chrome_leg", "chrome_leg_removal"),
    "chrome_hand": ("chrome_hand", "generic_removal"),
    # Sensory
    "chrome_eyes": ("chrome_eyes", "chrome_eyes_removal"),
    "chrome_eye_single": ("chrome_eye_single", "chrome_eyes_removal"),
    "audio_implant": ("audio_implant", "neural_implant_removal"),
    "olfactory_booster": ("olfactory_booster", "neural_implant_removal"),
    # Subdermal
    "subdermal_plating": ("subdermal_plating", "subdermal_removal"),
    "dermal_weave": ("dermal_weave", "subdermal_removal"),
    "bone_lacing": ("bone_lacing", "subdermal_removal"),
    "skin_weave": ("skin_weave", "subdermal_removal"),
    # Neural
    "wired_reflexes": ("wired_reflexes", "neural_implant_removal"),
    "synaptic_accelerator": ("synaptic_accelerator", "neural_implant_removal"),
    "pain_editor": ("pain_editor", "neural_implant_removal"),
    "threat_assessment": ("threat_assessment", "neural_implant_removal"),
    "memory_core": ("memory_core", "neural_implant_removal"),
    # Internal
    "cardiopulmonary_booster": ("cardiopulmonary_booster", "internal_implant_removal"),
    "adrenal_pump": ("adrenal_pump", "internal_implant_removal"),
    "toxin_filter": ("toxin_filter", "internal_implant_removal"),
    "metabolic_regulator": ("metabolic_regulator", "internal_implant_removal"),
    "hemostatic_regulator": ("hemostatic_regulator", "internal_implant_removal"),
    # Utility
    "voice_modulator": ("voice_modulator", "internal_implant_removal"),
    "grip_pads": ("grip_pads", "subdermal_removal"),
    "targeting_reticle": ("targeting_reticle", "neural_implant_removal"),
    "subvocal_comm": ("subvocal_comm", "internal_implant_removal"),
    "adrenaline_shunt": ("adrenaline_shunt", "internal_implant_removal"),
    "retractable_claws": ("retractable_claws", "subdermal_removal"),
    # Chrome organ replacements: generic chrome seating, internal removal.
    "chrome_heart": ("generic_implant", "internal_implant_removal"),
    "chrome_lungs": ("generic_implant", "internal_implant_removal"),
    "chrome_spine": ("generic_implant", "neural_implant_removal"),
    "chrome_liver": ("generic_implant", "internal_implant_removal"),
    "chrome_kidneys": ("generic_implant", "internal_implant_removal"),
    "chrome_throat": ("generic_implant", "internal_implant_removal"),
    "chrome_stomach": ("generic_implant", "internal_implant_removal"),
    "chrome_spleen": ("generic_implant", "internal_implant_removal"),
}


def get_install_narrative(surgery_narrative_key):
    """Return install narrative list for a given surgery key."""
    key = surgery_narrative_key or "generic_implant"
    mapped = NARRATIVE_KEY_MAP.get(key)
    install_key = mapped[0] if mapped else key
    return CYBERWARE_INSTALL_NARRATIVES.get(install_key, CYBERWARE_INSTALL_NARRATIVES["generic_implant"])


def get_removal_narrative(surgery_narrative_key):
    """Return removal narrative list for a given surgery key."""
    key = surgery_narrative_key or "generic_removal"
    mapped = NARRATIVE_KEY_MAP.get(key)
    removal_key = mapped[1] if mapped else key
    return CYBERWARE_REMOVAL_NARRATIVES.get(removal_key, CYBERWARE_REMOVAL_NARRATIVES["generic_removal"])


def get_narrative_step_count(surgery_narrative_key, is_removal=False):
    """Return the number of narrative steps for this procedure."""
    if is_removal:
        return len(get_removal_narrative(surgery_narrative_key))
    return len(get_install_narrative(surgery_narrative_key))

