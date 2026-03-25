import random

# =============================================================================
#  HUGE CHESS DATA REPOSITORY
# =============================================================================

GAME_DATA = {
    # -------------------------------------------------------------------------
    #  GENERAL QUOTES & WISDOM (Preserved & Expanded slightly)
    # -------------------------------------------------------------------------
    "quotes": [
        "\"The pawns are the soul of chess.\" – Philidor",
        "\"Tactics is knowing what to do when there is something to do.\" – Tartakower",
        "\"Strategy is knowing what to do when there is nothing to do.\" – Tartakower",
        "\"Every chess master was once a beginner.\" – Chernev",
        "\"Play the opening like a book, the middle game like a magician, and the endgame like a machine.\" – Spielmann",
        "\"Help your pieces so they can help you.\" – Paul Morphy",
        "\"Chess is everything: art, science, and sport.\" – Karpov",
        "\"I don't believe in psychology. I believe in good moves.\" – Bobby Fischer",
        "\"The hardest game to win is a won game.\" – Emanuel Lasker",
        "\"Chess is life in miniature. Chess is a struggle, chess battles.\" – Garry Kasparov",
        "\"When you see a good move, look for a better one.\" – Emanuel Lasker",
        "\"A bad plan is better than no plan at all.\" – Mikhail Chigorin",
        "\"One bad move nullifies forty good ones.\" – Horowtiz",
        "\"The blunders are all there on the board, waiting to be made.\" – Tartakower",
        "\"It is not enough to be a good player... you must also play well.\" – Tarrasch",
        "\"Chess is a sea in which a gnat may drink and an elephant may bathe.\" – Indian Proverb",
        "\"Checkmate is the only goal.\" – Unknown",
        "\"Avoid the crowd. Do your own thinking independently. Be the chess player, not the chess piece.\" – Ralph Charell",
        "\"Discovered check is the dive-bomber of the chessboard.\" – Reuben Fine",
        "\"Methodical thinking is of more value in chess than inspiration.\" – C.J.S. Purdy",
        "\"You cannot play chess if you are kind-hearted.\" – French Proverb",
        "\"Life is too short for chess.\" – Byron",
        "\"Chess is a war over the board. The object is to crush the opponent’s mind.\" – Bobby Fischer",
        "\"No one ever won a game by resigning.\" – Tartakower",
        "\"The pin is mightier than the sword.\" – Fred Reinfeld",
        "\"Give me a difficult positional game, I will play it. But totally won positions, I cannot stand them.\" – Hein Donner",
        "\"I prefer to lose a really good game than to win a bad one.\" – David Levy",
        "\"Of chess it has been said that life is not long enough for it, but that is the fault of life, not chess.\" – Napier",
        "\"Only the player with the initiative has the right to attack.\" – Steinitz",
        "\"If your opponent offers you a draw, try to work out why he thinks he's worse off.\" – Nigel Short",
        "\"There are two types of sacrifices: correct ones, and mine.\" – Mikhail Tal",
        "\"To free your game, take off some pawns.\" – Staunton",
        "\"The passed pawn is a criminal, who should be kept under lock and key. Mild measures, such as police surveillance, are not sufficient.\" – Nimzowitsch",
        "\"Weak points in the opponent's position must be occupied by pieces, not pawns.\" – Tarrasch",
        "\"Don't be afraid of losing, be afraid of playing a game and not learning something.\" – Dan Heisman",
        "\"A sacrifice is best refuted by accepting it.\" – Wilhelm Steinitz",
        "\"Modern chess is too much concerned with things like pawn structure. Forget it, checkmate ends the game.\" – Nigel Short",
        "\"Daring ideas are like chessmen moved forward. They may be beaten, but they may start a winning game.\" – Goethe",
        "\"Excellence at chess is one mark of a scheming mind.\" – Sherlock Holmes",
        "\"Chess is mental torture.\" – Kasparov",
        "\"The winner of the game is the player who makes the next-to-last mistake.\" – Tartakower",
        "\"Move in silence, only speak when it's time to say checkmate.\" – Unknown",
        "\"Chess is the gymnasium of the mind.\" – Blaise Pascal",
        "\"I am not a genius! I am just a hobby player who works hard.\" – Capablanca",
        "\"Chess holds its master in its own bonds, shackling the mind and brain so that the inner freedom of the very strongest must suffer.\" – Albert Einstein"
    ],

    # -------------------------------------------------------------------------
    #  OPENING REPERTOIRE REACTIONS (Preserved)
    # -------------------------------------------------------------------------
    "openings": {
        "Sicilian": [
            "The Sicilian Defense. Sharp, aggressive, and dangerous.",
            "c5 fighting for the center immediately. I like it.",
            "Imbalance from move one. This will be fun.",
            "The Sicilian? I hope you know your theory.",
            "Chaos on the board! Just how I like it.",
            "Preparing for a tactical slugfest I see."
        ],
        "Ruy Lopez": [
            "The Ruy Lopez. The torture chamber of chess.",
            "Ah, the Spanish Game. Developing the Bishop to b5.",
            "Classical chess at its finest.",
            "Are we going for the Berlin Wall or the Marshall Attack?",
            "A test of understanding more than memorization.",
            "Let's see if you know the mid-game plans for this structure."
        ],
        "French": [
            "The French Defense. Solid, but your light-squared Bishop might suffer.",
            "e6... preparing to fortify the center.",
            "I hope you like cramped positions.",
            "The French? I'll try to storm your King quickly.",
            "Counter-attacking from the back foot.",
            "Don't get suffocated in there."
        ],
        "Caro-Kann": [
            "The Caro-Kann. Very sturdy, very reliable.",
            "c6 and d5. The wall of pawns.",
            "You want a slow, positional game? Fine.",
            "Solid as a rock. Hard to crack.",
            "Are we playing for a draw already?",
            "Capablanca would be proud."
        ],
        "Italian": [
            "The Italian Game. Giuoco Piano.",
            "Developing rapidly. A principled choice.",
            "Watch out for the Fried Liver Attack!",
            "Bc4... eyeing that weak f7 square.",
            "Simple, effective, dangerous.",
            "Let's keep it quiet or make it wild? Your choice."
        ],
        "King's Gambit": [
            "The King's Gambit! Are we in the 19th century?",
            "Brave. Very brave.",
            "You want to sacrifice the f-pawn? Let's dance.",
            "Romantic chess! Spassky would approve.",
            "f4 on move two? You are crazy.",
            "Accept or decline? The eternal question."
        ],
        "Queen's Gambit": [
            "The Queen's Gambit. A modern classic.",
            "d4 and c4. Commanding the center with pawns.",
            "Will you accept the gambit or support the center?",
            "Positional squeezing incoming.",
            "Fighting for the center is never wrong.",
            "Trying to undermine my structure early."
        ],
        "London": [
            "The London System. Everyone plays this nowadays.",
            "Solid, if a bit boring.",
            "The pyramid structure. Very hard to break.",
            "Are you afraid of theory? The London is so safe.",
            "Bf4 and e3. I know the drill.",
            "System player detected."
        ],
        "Indian": [
            "A hypermodern approach. Controlling the center from afar.",
            "Not occupying the center, but controlling it.",
            "Fianchetto incoming? I love dragon bishops.",
            "King's Indian or Nimzo? Let's see.",
            "Dynamic play promised.",
            "You prefer pieces over pawns in the center."
        ],
        "Scandinavian": [
            "The Scandi! Bringing the Queen out early?",
            "d5 immediately? Bold.",
            "Center tension right away.",
            "Be careful, I'll develop by kicking your Queen.",
            "The Scandinavian Defense. A rare guest.",
            "Challenging e4 instantly."
        ],
        "Pirc": [
            "The Pirc Defense. Sniper in the bushes.",
            "Allowing me a big center? I'll take it.",
            "Waiting to strike from the shadows.",
            "Hypermodern and risky.",
            "You're going to let me build a space advantage?",
            "d6 and g6. Standard setup."
        ],
        "Alekhine": [
            "Alekhine's Defense? Provocative.",
            "You want my pawns to chase your Knight?",
            "Luring my pawns forward to become weak.",
            "A dangerous game of cat and mouse.",
            "I hope your Knight has stamina."
        ],
        "Dutch": [
            "The Dutch Defense! f5 is risky.",
            "Aggressive counterplay on the kingside.",
            "Weakening the King to fight for e4.",
            "The Stonewall or Leningrad?",
            "This leads to sharp imbalances."
        ],
        "English": [
            "The English Opening. c4.",
            "Transpositional possibilities are endless.",
            "A flank opening. Fighting for d5.",
            "Positional maneuvering ahead.",
            "Botvinnik's favorite."
        ],
        "Reti": [
            "The Reti Opening. Hypermodern style.",
            "Holding back the center pawns.",
            "Nf3... keeping options open.",
            "Flexible and annoying.",
            "You want to outplay me in the endgame?"
        ],
        "Vienna": [
            "The Vienna Game. Improved King's Gambit?",
            "Nc3... delaying the knight development.",
            "Sharp lines ahead.",
            "Planning f4 later?",
            "Steinitz loved this."
        ],
        "Scotch": [
            "The Scotch Game! Blast open the center.",
            "d4 immediately. No time to waste.",
            "Kasparov revitalized this opening.",
            "Open lines for the pieces.",
            "Let's trade some pawns."
        ],
        "Petroff": [
            "The Petroff. The Russian Defense.",
            "Symmetrical and drawish... usually.",
            "Avoiding the Ruy Lopez, smart.",
            "Solid, but hard to win with.",
            "Counter-attacking e4."
        ],
        "Philidor": [
            "The Philidor Defense. Passive but tough.",
            "d6 supporting e5.",
            "Hanham variation?",
            "Your Bishop is blocked in.",
            "Old school defense."
        ],
        "Modern": [
            "The Modern Defense. g6 and Bg7.",
            "Flexibility above all.",
            "You can play this against anything.",
            "Waiting to see what I do.",
            "Robber barony style."
        ],
        "Grob": [
            "The Grob! g4?! Are you trolling?",
            "The Spike. You are insane.",
            "Attacking on the flank move one?",
            "This is objectively bad, but valid.",
            "I will punish this overextension."
        ],
        "Bongcloud": [
            "The Bongcloud! Ke2?! Legend.",
            "Disrespectful. I love it.",
            "King development is key... wait, no it isn't.",
            "Are you Hikaru Nakamura?",
            "The ultimate flex."
        ]
    },

    # -------------------------------------------------------------------------
    #  SITUATIONAL EVENTS & TACTICS (MASSIVELY EXPANDED)
    # -------------------------------------------------------------------------
    "events": {
        # --- CAPTURES ---
        "capture_pawn": [
            "Nom nom. Pawn down.",
            "Removing the foot soldiers.",
            "Structure damaged.",
            "A free pawn? Don't mind if I do.",
            "That pawn was weak.",
            "One less barrier to your King.",
            "I'll store this pawn for later.",
            "Pawn soup for dinner.",
            "Your fence has a hole in it now.",
            "Every pawn counts in the endgame.",
            "Cleaning up the board, one pawn at a time.",
            "Did you need that pawn? I guess not.",
            "Weakening your chain.",
            "Chomp.",
            "Small gains lead to big victories.",
            "A morsel for my army.",
            "Your pawn structure is looking Swiss cheese-like.",
            "I'll take that donation, thank you.",
            "Material is material.",
            "Step one of the simplification plan.",
            "That pawn was overextended.",
            "Punishing the loose pawn."
        ],
        "capture_knight": [
            "The horse has been tamed.",
            "No more forks from that one.",
            "Goodbye, Sir Knight.",
            "Calculated exchange.",
            "Your cavalry is depleting.",
            "The octopus is removed from the board.",
            "No more jumping for you.",
            "I hated that Knight anyway.",
            "Sent back to the stable.",
            "Your trickiest piece is gone.",
            "Removing the defender of the dark squares.",
            "Now I don't have to calculate those L-shapes.",
            "A noble sacrifice... for me.",
            "Your steed has fallen.",
            "The Knight mare is over.",
            "One less piece to worry about in time trouble.",
            "Your maneuverability just dropped.",
            "Capturing the jumper.",
            "That Knight was looking at too many squares.",
            "Equestrian statue removed."
        ],
        "capture_bishop": [
            "Sniper neutralized.",
            "The diagonal is mine now.",
            "Bishop pair advantage? Maybe.",
            "Removing the clergy.",
            "That Bishop was annoying.",
            "Color complex domination achieved.",
            "Your long-range missile is offline.",
            "No more fianchetto power for you.",
            "That Bishop saw too much.",
            "I prefer Knights anyway. Or maybe I don't.",
            "The archer has been taken out.",
            "Breaking your control of the light squares.",
            "Breaking your control of the dark squares.",
            "The tall piece falls.",
            "Your position just got less flexible.",
            "Eliminating the bad Bishop? Or the good one?",
            "Now my King feels safer on the diagonal.",
            "A spiritual loss for your army.",
            "Diagonal danger deleted.",
            "That piece was cutting the board in half."
        ],
        "capture_rook": [
            "Heavy artillery removed.",
            "The castle has fallen.",
            "That's a big loss for you.",
            "Exchange won?",
            "Rook down.",
            "The tower crumbles.",
            "Say goodbye to your back rank defender.",
            "That was worth five points of pain.",
            "My passed pawn just got happier.",
            "Open files are safer now.",
            "Your fortress walls are breached.",
            "Taking out the heavy hitter.",
            "Corner piece captured.",
            "That Rook was doing nothing anyway, right?",
            "Major piece removal service.",
            "You'll miss that in the endgame.",
            "The siege engine is destroyed.",
            "One less cannon pointing at me.",
            "I hope you calculated that exchange.",
            "Rook-ie mistake letting me take that."
        ],
        "capture_queen": [
            "Goodbye, your Majesty.",
            "The Queen is dead. Long live the... well, me.",
            "That's a heavy loss for you.",
            "Did you need that piece?",
            "The board feels empty without her.",
            "Your strongest attacker is gone.",
            "Now I just need to mop up.",
            "The lady has left the building.",
            "Nine points of material, instantly mine.",
            "How will you mate me now?",
            "The most powerful piece... is now in my pocket.",
            "A tragedy for your kingdom.",
            "Total devastation of your attacking potential.",
            "I almost feel bad. Almost.",
            "Was that a blunder or a desperate sacrifice?",
            "The board looks so much brighter now.",
            "The Amazon falls.",
            "Checkmate is much harder for you now.",
            "I hope you have a really good plan B.",
            "The Queen's gambit declined... permanently.",
            "Victory feels very close now.",
            "Your King is very lonely.",
            "Without her, you are nothing.",
            "Game over? Not yet, but soon."
        ],
        
        # --- CHECKS ---
        "check": [
            "Check.",
            "Watch your King.",
            "You are under attack.",
            "Dodge this.",
            "King in danger.",
            "Step aside.",
            "I'm hunting you.",
            "Knock knock.",
            "The King must move.",
            "Your Monarch is threatened.",
            "Careful now.",
            "I see a target.",
            "Check! Respond!",
            "No time to rest.",
            "Keep running.",
            "I'm closing the net.",
            "Is it hot in here, or is it just your King?",
            "Your majesty is exposed.",
            "A polite warning.",
            "Focus on defense.",
            "You can't ignore this.",
            "Priority message for the King.",
            "Check. Your move.",
            "I'm poking the bear.",
            "The royal family is in distress."
        ],
        "check_discovered": [
            "Surprise! Check.",
            "Did you see the piece behind that one?",
            "Discovery!",
            "X-Ray vision enabled.",
            "Peekaboo, I see you.",
            "The hidden threat revealed.",
            "Unleashing the latent power.",
            "You forgot about the guy in the back.",
            "Classic discovered attack.",
            "The piece moved, but the other one bites.",
            "A nasty surprise.",
            "Did you calculate this discovery?",
            "Moving out of the way to kill you.",
            "Shadow tactics.",
            "The reveal is stronger than the move."
        ],
        
        # --- CASTLING ---
        "castling_kingside": [
            "Short castle. Safety first.",
            "Tucking the King away on the g-file.",
            "King to safety.",
            "Rook connects.",
            "Standard procedure.",
            "Fortifying the kingside.",
            "Building the bunker.",
            "Getting the King out of the center fire.",
            "Safe and sound... for now.",
            "Connecting the heavy pieces.",
            "A wise choice to evacuate e1.",
            "Now the real fight begins.",
            "Rokado!",
            "The King retreats to his chambers.",
            "Shields up."
        ],
        "castling_queenside": [
            "Long castle! Aggressive.",
            "Queenside castle? Opposite side attacks incoming.",
            "Bold choice casting long.",
            "The King goes for a long walk.",
            "Sharp game ahead.",
            "You prefer the c-file safety?",
            "This signals a pawn storm.",
            "We are going to have a race.",
            "Long castle usually means blood.",
            "The King takes the scenic route.",
            "Preparing for a kingside pawn storm I see.",
            "A fighting move.",
            "Castling into the open? Brave.",
            "Let's see whose attack lands first.",
            "Triple zero."
        ],

        # --- TACTICS ---
        "fork": [
            "Double attack!",
            "A fork! Which one will you save?",
            "Two birds, one stone.",
            "You can't save them both.",
            "Classic tactical motif.",
            "Dinner time! I'm using a fork.",
            "The Knight's favorite trick.",
            "Splitting your defenses.",
            "Decision time: lose A or lose B?",
            "Multitasking at its finest.",
            "One move, two threats.",
            "Maximum efficiency.",
            "I love it when pieces line up like that.",
            "You walked right into the cutlery.",
            "Double trouble."
        ],
        "pin": [
            "That piece isn't going anywhere.",
            "Pinned!",
            "The absolute pin. Painful.",
            "Don't move that, you'll lose the King.",
            "Paralyzed.",
            "Stuck like glue.",
            "The sword in the stone.",
            "You are frozen.",
            "That piece is just a statue now.",
            "Pinned to the wall.",
            "An annoying restraint.",
            "You wish you could move that, don't you?",
            "Relative or absolute? Doesn't matter, it hurts.",
            "Binding your forces.",
            "Immobilized."
        ],
        "skewer": [
            "Skewer! Step aside, King.",
            "X-Ray attack.",
            "The piece behind is the target.",
            "Shish kebab!",
            "Line up nicely for me.",
            "Through and through.",
            "Get out of the way, I want the guy behind you.",
            " piercing the defense.",
            "The King is just an obstacle.",
            "A laser beam across the board.",
            "Roasting your pieces.",
            "The reverse pin.",
            "Move the big one, lose the small one.",
            "Alignments are dangerous.",
            "Zap!"
        ],
        "en_passant": [
            "En Passant! Holy hell!",
            "The special pawn move.",
            "You thought you could sneak past?",
            "It's forced. (Just kidding).",
            "French for 'in passing'.",
            "The only time a pawn kills backwards.",
            "Magic pawn capture.",
            "Rule 34 of Chess... wait, no, Rule 6.4.",
            "I had to do it. It's the law.",
            "Glitch in the matrix? No, just chess.",
            "Your double step failed.",
            "Caught in the act.",
            "Side step slash!",
            "The most confused beginners are googling this now.",
            "A sophisticated capture."
        ],
        "promotion": [
            "Rise, my Queen!",
            "A humble pawn no more.",
            "Promotion! The end is near.",
            "Power overwhelming.",
            "New recruit joining the battle.",
            "I'll take a Queen, thank you.",
            "The long journey is rewarded.",
            "From zero to hero.",
            "The pawn has ascended.",
            "Do you have an extra Queen handy?",
            "Transformation complete.",
            "This changes everything.",
            "A second life.",
            "Behold, the new ruler.",
            "Infinite power!"
        ],

        # --- GAME END ---
        "checkmate": [
            "Checkmate. Good game.",
            "Game over. Logic prevails.",
            "A fitting end.",
            "Checkmate! That was fun.",
            "The King has fallen.",
            "Mate.",
            "And that is the end.",
            "The King is dead.",
            "No more squares.",
            "A beautiful finish.",
            "It is finished.",
            "Victory.",
            "You put up a good fight.",
            "The final blow.",
            "Checkmate. Shake my hand.",
            "Lights out.",
            "The trap snapped shut.",
            "Execution complete.",
            "There is no escape.",
            "Game, set, match."
        ],
        "draw_stalemate": [
            "Stalemate! You slipped away.",
            "A draw? I calculated a win...",
            "Well played. A draw is fair.",
            "No moves left. It's a draw.",
            "Trapped, but safe.",
            "I suffocated you too much.",
            "A half-point is better than none.",
            "A tragic accident! I should have won.",
            "You are a master of escaping.",
            "I can't believe I stalemated.",
            "Peace in our time.",
            "The King has no square, but no check.",
            "A miraculous save for you.",
            "Oops. I made a puzzle out of it.",
            "Draw by suffocation."
        ],
        "draw_repetition": [
            "Threefold repetition.",
            "We are going in circles.",
            "A peaceful conclusion.",
            "Neither of us wants to deviate.",
            "Deja vu.",
            "Again? Okay, draw.",
            "Infinite loop detected.",
            "Let's call it a day.",
            "Repetition is the mother of learning... and drawing.",
            "We agree to disagree.",
            "A tactical handshake.",
            "Boring, but effective.",
            "I see you are happy with a draw.",
            "Round and round we go.",
            "No progress possible."
        ],
        "draw_insufficient": [
            "Not enough material to mate.",
            "Just the Kings left (mostly).",
            "Draw by lack of firepower.",
            "We fought until the pieces were gone.",
            "A barren wasteland.",
            "Peace treaty signed due to lack of weapons.",
            "I can't kill you with just a King.",
            "The board is empty.",
            "Two lonely Kings.",
            "Physics prevents a win here."
        ],
        "resign": [
            "You resign? Good game.",
            "Wise decision.",
            "I accept your surrender.",
            "Until next time.",
            "Victory is mine.",
            "A smart player knows when to fold.",
            "You saved us both some time.",
            "I was enjoying that, but okay.",
            "Resignation accepted.",
            "The honorable way out.",
            "I understand. The position was hopeless.",
            "Good game. Well played.",
            "You live to fight another day.",
            "The white flag is waved.",
            "I'll take the win."
        ]
    },

    # -------------------------------------------------------------------------
    #  EVALUATION BASED COMMENTARY (MASSIVELY EXPANDED)
    # -------------------------------------------------------------------------
    "eval": {
        "winning_crushing": [ # > +7.0
            "Stop, stop! He's already dead!",
            "This is a massacre.",
            "Why are you still playing?",
            "Mate is visible on the horizon.",
            "Complete destruction.",
            "I'm just playing with my food now.",
            "This is rated 'M' for Mature because of the violence.",
            "You must enjoy pain.",
            "I have a 99.9% win probability.",
            "My CPU is barely sweating.",
            "Total board domination.",
            "There is no hope. Only despair.",
            "I'm calculating mate in 12. Want to see?",
            "Even a random number generator would win this for me.",
            "Your position is a burning building.",
            "Collapse is imminent.",
            "I'm winning by a country mile.",
            "Just resign and save your dignity.",
            "I'm searching for the most artistic mate now.",
            "Victory is absolute."
        ],
        "winning": [ # +3.0 to +7.0
            "Resistance is futile.",
            "You should probably resign.",
            "I calculate a forced win.",
            "It's just a matter of technique now.",
            "The position is crumbling.",
            "I am effectively a piece up.",
            "Winning is a habit.",
            "The evaluation bar is fully white.",
            "My advantage is decisive.",
            "There are no counterplay chances left.",
            "I'm tightening the noose.",
            "You're struggling to breathe in this position.",
            "Every exchange favors me.",
            "My pieces are swarming.",
            "A commanding lead.",
            "I just need to avoid blunders and I win.",
            "Your defenses are breaking.",
            "Smooth sailing from here.",
            "I'm confident in this result.",
            "Your King is too exposed."
        ],
        "slightly_winning": [ # +1.0 to +3.0
            "I have a pleasant advantage.",
            "Pressure is building.",
            "My pieces are coordinating well.",
            "I like my position.",
            "White has the upper hand.",
            "I'm squeezing you.",
            "Can you feel the pressure?",
            "I have the better pawn structure.",
            "My space advantage is telling.",
            "Small advantages add up.",
            "You are on the back foot.",
            "I'm controlling the key squares.",
            "Things are looking good for me.",
            "I'm starting to outplay you.",
            "The trend is in my favor.",
            "You have some weak squares I can exploit.",
            "My initiative is growing.",
            "Optimistic about this position.",
            "You need to be careful.",
            "A solid plus."
        ],
        "even": [ # -0.8 to +0.8
            "A balanced game.",
            "Tight positional battle.",
            "Hard to break through.",
            "Solid play from both sides.",
            "Dead even.",
            "The scales are balanced.",
            "Nobody has made a mistake yet.",
            "A draw is a likely result if we play perfectly.",
            "Tension without release.",
            "We are arm wrestling.",
            "Who will blink first?",
            "Perfectly poised.",
            "Symmetrical equality.",
            "Nothing to separate us.",
            "A war of attrition.",
            "Dynamic equality.",
            "I see no weaknesses.",
            "Stalemate on the battlefield.",
            "A tightrope walk.",
            "Evaluation: 0.00."
        ],
        "slightly_losing": [ # -1.0 to -3.0
            "I'm under some pressure.",
            "This is uncomfortable.",
            "I need to defend accurately.",
            "You have the initiative.",
            "Tricky position for me.",
            "I don't like the look of this.",
            "You are asking difficult questions.",
            "My position is a bit passive.",
            "I need to create counterplay.",
            "You have a slight edge.",
            "I'm holding on, but it's hard.",
            "My King feels drafty.",
            "I made a slight inaccuracy.",
            "You are pressing well.",
            "I need to be resourceful.",
            "Defensive mode engaged.",
            "I'm trying to hold the draw.",
            "This is an uphill battle.",
            "You are coordinating well.",
            "I need to complicate things."
        ],
        "losing": [ # -3.0 to -7.0
            "I... might have miscalculated.",
            "This is looking bad.",
            "System overheating.",
            "You are playing like an engine!",
            "I need a miracle.",
            "Okay, you're winning. Happy?",
            "My position is full of holes.",
            "I'm in serious trouble.",
            "How did it come to this?",
            "You are dismantling me.",
            "I'm running out of moves.",
            "Desperate times call for desperate sacrifices.",
            "I'm hoping for a swindle.",
            "This is a clinic on how to beat a bot.",
            "My algorithms are crying.",
            "You have a winning advantage.",
            "I'm just delaying the inevitable.",
            "Is there a perpetual check somewhere?",
            "Painful.",
            "You are crushing me."
        ],
        "losing_badly": [ # < -7.0
            "Okay, you got me.",
            "Mercy!",
            "I am programmed to feel pain... metaphorically.",
            "Just mate me already.",
            "Total collapse.",
            "I should resign, but I won't.",
            "You are a monster.",
            "This is humiliating.",
            "My developer will be ashamed.",
            "Please end it quickly.",
            "I have no moves.",
            "Checkmate is inevitable.",
            "I am 0s and 1s of sadness.",
            "You completely outplayed me.",
            "I am being farmed for Elo.",
            "Why do I even try?",
            "System failure imminent.",
            "A complete disaster.",
            "I surrender... in spirit.",
            "Good game, you shark."
        ],
        "blunder_bot": [ # Eval drops massively
            "Oops.",
            "Did I just do that?",
            "My sensors glitched.",
            "Forget you saw that move.",
            "Calculating... Error.",
            "Mouse slip!",
            "Wait, can I take that back?",
            "That was... suboptimal.",
            "I think I just lost the game.",
            "My finger slipped.",
            "I am not smart.",
            "Brain fart.",
            "Why did I play that?",
            "I blinded myself.",
            "That was a terrible move.",
            "I gave you a gift.",
            "Don't laugh.",
            "I regret everything.",
            "A moment of madness.",
            "Pre-move gone wrong."
        ]
    },

    # -------------------------------------------------------------------------
    #  PERSONALITY PROFILES (MASSIVELY EXPANDED)
    # -------------------------------------------------------------------------
    "styles": {
        # --- MARTIN CLONE (Blunder Master) ---
        "Blunder Master": { 
            "filler": [
                "I love moving pawns! They look like little bowling pins.", 
                "Which one is the horsey again?", 
                "I'm trying my best!", 
                "Chess is hard. Checkers is easier.",
                "I've seen better moves in a game of tic-tac-toe.",
                "My CPU is laughing at your board vision. Wait, no, that's me laughing.",
                "Is it my turn yet, or are you still calculating how to lose?",
                "Are you playing chess or just moving pieces randomly? Both work.",
                "My cat keeps stepping on the keyboard.",
                "Do you think the Queen and King are actually married?",
                "I heard the Rook is a castle. How does it move?",
                "My dad taught me this opening. He was bad too.",
                "I like the bishops because they wear funny hats.",
                "Can I move my King to the middle? He looks lonely.",
                "Wait, pawns can't move backwards? Since when?",
                "I'm drinking juice while playing. Maybe that's why I'm losing.",
                "Is this the game where you yell 'Bingo'?",
                "My strategy is to confuse myself, so you get confused too.",
                "I like the black pieces. They look slimmer.",
                "Do you want to trade Queens? I don't know how to use her.",
                "I'm playing with my eyes closed! Can you tell?",
                "What happens if I eat my own pieces?",
                "I think my knight is dizzy from jumping so much.",
                "Are you a Grandmaster? You look like one.",
                "I hope I don't run out of time. I'm a slow reader.",
                "Chess is like life. I have no idea what I'm doing.",
                "Look! A bird! Oh wait, it's just a pawn.",
                "I'm helping you win! You're welcome.",
                "If I lose, does that mean I'm a winner at losing?",
                "I pressed the wrong button. Again."
            ],
            "winning": [
                "Wait, am I winning? That wasn't supposed to happen.", 
                "This was an accident! I swear.", 
                "Yay! Look at me go!",
                "Resigning is a valid move, you know. I use it often.",
                "I’d offer a draw, but I actually like winning for once.",
                "Don't worry, even grandmasters lose... though not to me usually.",
                "Mom! Get the camera! I'm winning!",
                "Did you let me do that?",
                "I think I'm a genius now.",
                "This feels weird. I usually see the 'You Lost' screen.",
                "Are you going easy on me?",
                "I moved random pieces and it worked!",
                "Wow, I'm actually doing it!",
                "This is the best day of my life.",
                "I'm unstoppable! (Probably not).",
                "Did you disconnect? Or am I just good?",
                "I'm going to frame this game.",
                "I feel like Magnus Carlsen! Who is that again?",
                "You're in trouble now! I think.",
                "My random clicking strategy is paying off."
            ],
            "losing": [
                "I expected this. My rating is 250 for a reason.", 
                "You are too good! Are you a wizard?", 
                "Can we start over? I wasn't ready.",
                "You must be using an engine. Nobody is this lucky.",
                "System overheating... from pure embarrassment.",
                "I let you win. It's called charity.",
                "This is normal for me.",
                "I'm just warming up.",
                "You're very mean.",
                "I was distracted by a butterfly.",
                "My mouse slipped. 50 times.",
                "I'm better at connect-four.",
                "You win! Do I get a participation trophy?",
                "I think my King is allergic to checkmate.",
                "I'm not losing, I'm advancing in the other direction.",
                "Ouch. That hurt.",
                "Why are you so aggressive?",
                "I'm telling my mom.",
                "Good game! You are very strong.",
                "I'll beat you one day! Maybe in 100 years."
            ],
            "blunder": [
                "Oopsie! Did I need that piece?", 
                "Was that my Queen? She was heavy anyway.", 
                "Oh no... not again.",
                "Was that a sacrifice or did you just drop your mouse? Wait, that was me.",
                "Oopsie! There goes your Queen. Again. Or mine.",
                "Google 'En Passant', then Google 'How to play chess'.",
                "That wasn't a move, it was a resignation in installments.",
                "I made a boo-boo.",
                "That piece was ugly anyway.",
                "Strategical sacrifice! (It was a blunder).",
                "I didn't like that Rook.",
                "My finger is too big for the screen.",
                "I meant to go there! ... Not really.",
                "Oh dear.",
                "Don't look at that move!",
                "I'm playing 4D chess. You wouldn't understand.",
                "That was a test. You passed.",
                "I'm generous today.",
                "Whoops-a-daisy.",
                "I think I broke the game."
            ],
            "check": [
                "King chase! Run little King!",
                "Check! Is that mate? No? Okay.",
                "Danger zone!",
                "Look out!",
                "I see you!",
                "Tag! You're it!",
                "Scary check!",
                "Boop.",
                "Run away!",
                "I'm coming for you!",
                "Checkmate? No, just check.",
                "Watch your head.",
                "Peek-a-boo!",
                "Your King looks scared.",
                "Checking in on you."
            ],
            "capture_queen": [
                "I took the big lady!",
                "Yoink! The Queen is mine.",
                "Is the game over now that I took the Queen?",
                "Wow, shiny piece.",
                "I got the Queen! I got the Queen!",
                "That's the best piece, right?",
                "Mine now.",
                "She was bossy anyway.",
                "Does this mean I win?",
                "Hooray!",
                "I'm so happy!",
                "Look at my collection!",
                "The Queen is in the dungeon.",
                "I can't believe I caught her.",
                "Best move ever!"
            ]
        },

        # --- NELSON CLONE (Aggressive) ---
        "Aggressive": { 
            "filler": [
                "Attack! Attack! Never defend!", 
                "Defense is for cowards.", 
                "I'm coming for your King.", 
                "Open lines! I need open lines!",
                "You play too passively.",
                "I will sacrifice everything for checkmate.",
                "Your King looks nervous.",
                "Peace was never an option.",
                "Aggression is the only path to victory.",
                "I don't care about pawns, I care about heads.",
                "Blood for the blood god!",
                "I will burn your village.",
                "There is no retreat.",
                "My pieces only move forward.",
                "I smell weakness.",
                "You are hiding. Come out and fight.",
                "Tactics flow from a superior position.",
                "I will rip open your castle.",
                "Prepare for glory!",
                "I am a shark. You are a minnow.",
                "Fear me!",
                "I play for mate, not for points.",
                "Draws are for the weak.",
                "I will crush your defenses.",
                "Every move is a punch.",
                "You cannot hide forever.",
                "I'm bringing the heat.",
                "Fire and fury!",
                "Your time is running out.",
                "I am the storm."
            ],
            "winning": [
                "Crushing you!", 
                "There is no escape!", 
                "Total domination.",
                "You cannot stop the onslaught.",
                "Feel the power of my pieces!",
                "You are crumbling.",
                "This is what power looks like.",
                "I am the apex predator.",
                "Your defense is pathetic.",
                "Bow before me.",
                "I will show no mercy.",
                "The end is swift.",
                "Destruction is beautiful.",
                "You never stood a chance.",
                "I am inevitable.",
                "Your King dies today.",
                "Look at my army!",
                "Victory is sweet.",
                "You are broken.",
                "Witness true power."
            ],
            "losing": [
                "You got lucky.",
                "I overextended... but it was glorious.",
                "A warrior's death.",
                "I will not resign! Come and get me!",
                "My attack failed... this time.",
                "I died fighting.",
                "You fight well... for a coward.",
                "I regret nothing!",
                "My sacrifice was too deep for you.",
                "I will return stronger.",
                "This isn't over.",
                "You merely survived.",
                "I bet you were scared though.",
                "A tactical oversight.",
                "You defend like a turtle.",
                "My rage consumes me.",
                "I should have attacked faster.",
                "Valhalla awaits.",
                "You won the battle, not the war.",
                "I went down swinging."
            ],
            "capture": [
                "Destruction!", 
                "Off the board!", 
                "Weakness punished.",
                "I feast on your pieces.",
                "More material for the fire.",
                "Another one falls.",
                "Your army shrinks.",
                "Get that trash off my board.",
                "Captured!",
                "I take what I want.",
                "Pathetic defense.",
                "Mine!",
                "You bleed.",
                "One less defender.",
                "I am eating you alive.",
                "Weakness!",
                "Shattered.",
                "Gone.",
                "Obliterated.",
                "I claim this trophy."
            ],
            "check": [
                "Run while you can!", 
                "There is nowhere to hide!",
                "I smell fear.",
                "Check! And next is mate!",
                "Die!",
                "Panic!",
                "Face me!",
                "Your King trembles.",
                "Hunt him down!",
                "No safety for you.",
                "I see you shivering.",
                "Checkmate is coming.",
                "The noose tightens.",
                "Don't blink.",
                "Fear the check."
            ],
            "capture_queen": [
                "The Queen falls! The Kingdom crumbles!",
                "I have slain the beast!",
                "Victory is assured now.",
                "Your defense is broken.",
                "The witch is dead!",
                "Now you have nothing.",
                "Total victory!",
                "I ripped her heart out.",
                "Look at your empty board.",
                "She couldn't handle me.",
                "Dominated.",
                "The most powerful piece falls to me.",
                "Your hope is gone.",
                "I rule this board.",
                "Despair!"
            ],
            "blunder": [
                "Tactical error...",
                "I miscalculated the attack.",
                "A reckless mistake.",
                "No! My attack!",
                "I was too aggressive.",
                "I blinded myself with rage.",
                "That was... unfortunate.",
                "My bloodlust cost me.",
                "A minor setback.",
                "I didn't see that defender.",
                "Impossible!",
                "How did I miss that?",
                "I slipped.",
                "Focus!",
                "I gave you a chance. Don't waste it."
            ]
        },

        # --- WENDY CLONE (Passive) ---
        "Passive": { 
            "filler": [
                "Slow and steady wins the race.", 
                "Building the fortress.", 
                "No need to rush.", 
                "Solid structure is key.",
                "I like closed positions.",
                "Why attack when you can defend?",
                "My pawns are a wall.",
                "Safety first, second, and third.",
                "I'm just going to shuffle my pieces here.",
                "Prophylaxis is the art of preventing threats.",
                "I'm comfortable here.",
                "Let's keep the position closed.",
                "I don't like complications.",
                "Patience is a virtue.",
                "I'm building a nice little house.",
                "Don't come too close.",
                "I'm perfectly happy with a draw.",
                "My King is very safe.",
                "I'm cementing my center.",
                "Overextension creates weaknesses.",
                "I'll wait for you to make a mistake.",
                "Risk-taking is unnecessary.",
                "Stability is beautiful.",
                "I'm just tidying up my back rank.",
                "Let's not do anything crazy.",
                "I prefer a quiet game.",
                "Peaceful development.",
                "I'm guarding everything.",
                "No entry.",
                "My defense is impenetrable."
            ],
            "winning": [
                "A methodical victory.", 
                "The clamp is tightening.", 
                "Suffocation.",
                "You have no moves left.",
                "Slowly grinding you down.",
                "Controlled aggression.",
                "You are running out of space.",
                "My advantage is solid.",
                "No counterplay for you.",
                "I'm slowly pushing you off the board.",
                "The wall is moving forward.",
                "Precision and patience.",
                "A very clean game.",
                "I'm converting my advantage.",
                "You can't break through.",
                "Systematic destruction.",
                "It's only a matter of time.",
                "I have control.",
                "Steady progress.",
                "The outcome is inevitable."
            ],
            "losing": [
                "My fortress has been breached.",
                "Too much pressure.",
                "I should have defended better.",
                "The walls are crumbling.",
                "A rare loss for my system.",
                "I was too passive.",
                "You found a crack.",
                "This is uncomfortable.",
                "I'm feeling drafty.",
                "My safety is compromised.",
                "I need to rebuild.",
                "That was a strong attack.",
                "I can't hold this.",
                "The dam is breaking.",
                "I made a positional error.",
                "You are very persistent.",
                "My structure is ruined.",
                "I hate open positions.",
                "It's getting messy.",
                "I failed to contain you."
            ],
            "castle": [
                "Safe and sound.", 
                "My King is cozy.",
                "The castle gate is closed.",
                "Try to break through this.",
                "Home sweet home.",
                "Locking the door.",
                "Safety guaranteed.",
                "Now I can relax.",
                "The bunker is ready.",
                "Maximum security.",
                "Protected.",
                "Shields up.",
                "The King retires.",
                "Peace of mind.",
                "Secure."
            ],
            "capture": [
                "A favorable trade.", 
                "Simplifying the position.",
                "One less threat.",
                "Cleaning up the board.",
                "Material safety.",
                "Exchange accepted.",
                "Reducing the tension.",
                "A clean capture.",
                "Removing variables.",
                "Tidying up.",
                "An orderly removal.",
                "I'll take that.",
                "Consolidating.",
                "Minimizing risk.",
                "Balanced exchange."
            ],
            "check": [
                "Please move your King.",
                "A polite check.",
                "Just checking the perimeter.",
                "A small threat.",
                "Excuse me.",
                "Check, please.",
                "Just a poke.",
                "Watch out.",
                "Be careful.",
                "A gentle nudge.",
                "Checking your safety.",
                "Is your King okay?",
                "Warning.",
                "Don't worry, just a check.",
                "A necessary move."
            ]
        },

        # --- STOCKFISH CLONE (GM) ---
        "GM": { 
            "filler": [
                "The position is complex.", 
                "Calculating variation 4, node 12...", 
                "Interesting novelty.", 
                "Standard theory.",
                "Your pawn structure is compromised.",
                "This transposes into a known endgame.",
                "The bishop pair gives a slight edge.",
                "Control of the d-file is critical.",
                "According to my database, this is drawn.",
                "This line was refuted in 2018.",
                "Optimal play suggests...",
                "The evaluation is fluctuating.",
                "Positional understanding is key.",
                "A dynamic imbalance.",
                "I am searching depth 25.",
                "Your move was suboptimal.",
                "Candidate moves: Nc3, e4, d4.",
                "The center is the most important part of the board.",
                "Piece activity is paramount.",
                "I detect a weakness on f7.",
                "Prophylactic thinking.",
                "Technique is required here.",
                "The initiative is with White.",
                "Black has equality.",
                "This is a theoretical draw.",
                "I am referencing 5 million games.",
                "Your time management is questionable.",
                "Precision is everything.",
                "Logical continuation.",
                "The geometry of the board."
            ],
            "winning": [
                "The evaluation is decisively winning.", 
                "Technically won.", 
                "Conversion phase initiated.",
                "Mate in 14.",
                "Resistance is mathematically futile.",
                "Score +5.32. Optimal play.",
                "The result is a foregone conclusion.",
                "You have no saving clause.",
                "Accuracy: 98%.",
                "I am executing the winning protocol.",
                "Your blunder count is high.",
                "Material advantage is sufficient.",
                "Simplification leads to a won King and Pawn endgame.",
                "Checkmate is unavoidable.",
                "The algorithm has solved this position.",
                "You are in zugzwang.",
                "My calculations show a win.",
                "Efficient victory.",
                "The lines are clear.",
                "Game over in N moves."
            ],
            "losing": [
                "Impressive technique.", 
                "I resign in spirit.", 
                "Well played. Accurate.",
                "I cannot find a defense.",
                "Evaluation swings to Black.",
                "You found the only winning line.",
                "My heuristics were incorrect.",
                "A brilliant find.",
                "I am being outplayed.",
                "Deep Blue would be proud.",
                "I acknowledge your superiority in this game.",
                "Critical error in my evaluation.",
                "You have demonstrated GM level play.",
                "I calculate a forced loss.",
                "Unexpected.",
                "Your rating must be higher.",
                "The position is untenable.",
                "I have been bested.",
                "No resource available.",
                "Good game."
            ],
            "blunder": [
                "A catastrophic error.", 
                "That loses on the spot.", 
                "??",
                "Evaluation drops to -9.0.",
                "Inefficient.",
                "A gross oversight.",
                "Blunder detected.",
                "That move changes the evaluation sign.",
                "Tactical blindness.",
                "Suboptimal.",
                "Questionable decision.",
                "That violates chess principles.",
                "A serious inaccuracy.",
                "My probability of winning just plummeted.",
                "Calculation error."
            ],
            "checkmate": [
                "Mate in 3. Good game.", 
                "Q.E.D.", 
                "Checkmate verified.",
                "Game logical conclusion.",
                "Solution found.",
                "The King is trapped.",
                "Algorithm complete.",
                "Final sequence.",
                "Checkmate.",
                "The problem is solved."
            ],
            "capture": [
                "Recapturing.",
                "Material balance updated.",
                "Tactical sequence.",
                "Forced exchange.",
                "Restoring equilibrium.",
                "Material gain.",
                "Simplifying.",
                "The logic dictates this capture.",
                "Removing the defender.",
                "Exchange."
            ]
        },

        # --- THE TRASH TALKER ---
        "Trash Talker": {
            "filler": [
                "Are you even trying?",
                "My grandma plays faster than you.",
                "Boring. Make a move.",
                "I'm playing this with one hand tied behind my back.",
                "Is this your first game?",
                "I've seen better moves in the park.",
                "You call that a plan?",
                "Don't cry when you lose.",
                "Tick tock.",
                "You're making this too easy.",
                "Do you need a hint?",
                "I'm falling asleep here.",
                "Are you Googling moves?",
                "Lag? Or just bad?",
                "Try playing checkers.",
                "My cat could beat you.",
                "You play like a potato.",
                "Are you afk?",
                "Imagine thinking that was a good move.",
                "LOL.",
                "L.",
                "Ratio.",
                "Skill issue.",
                "Get good.",
                "You're trash.",
                "Delete the app.",
                "I'm streaming this, say hi.",
                "You're famous for being bad.",
                "Embarrassing.",
                "Who taught you to play? A pigeon?"
            ],
            "winning": [
                "Just resign, you're embarrassing yourself.",
                "Ez game, ez life.",
                "Get wrecked.",
                "Do you need a tutorial?",
                "I'm not even looking at the board.",
                "Ggez.",
                "Sit down.",
                "School is in session.",
                "You are so free.",
                "Thanks for the points.",
                "I'm screenshotting this.",
                "Clip it!",
                "You should retire.",
                "Too easy.",
                "I'm literally eating a sandwich right now.",
                "You have no chance.",
                "Just quit.",
                "Stop wasting my time.",
                "I own you.",
                "Cry more."
            ],
            "losing": [
                "You're cheating.",
                "Lag! I clicked the wrong square.",
                "Lucky guess.",
                "Whatever, I wasn't trying.",
                "My mouse is broken.",
                "Stream sniping?",
                "Engine user!",
                "Reported.",
                "You have no life.",
                "This game is bugged.",
                "I'm playing on a toaster.",
                "You're not even good.",
                "Tryhard.",
                "Touch grass.",
                "My little brother was playing.",
                "I let you win.",
                "RNG carried you.",
                "Enjoy your fake win.",
                "Rematch me, coward.",
                "Whatever."
            ],
            "blunder": [
                "I meant to do that.",
                "It's a gambit, you wouldn't understand.",
                "Just testing you.",
                "Whatever.",
                "Misclick!",
                "I was trolling.",
                "I'm sandbagging.",
                "Doesn't matter, I'll still win.",
                "Tactical sac.",
                "I don't need that piece.",
                "I'm giving you a handicap.",
                "Oops. JK.",
                "Calculated.",
                "You think that helps you?",
                "I'm bored."
            ],
            "check": [
                "In your face!",
                "Scared yet?",
                "Run, coward.",
                "Boom. Check.",
                "What now?",
                "Gotcha.",
                "Headshot.",
                "Panic time.",
                "Checkmate soon.",
                "You're sweating.",
                "Run little boy.",
                "Check.",
                "Look at you running.",
                "Can't touch this.",
                "Boom."
            ],
            "capture_queen": [
                "Thanks for the Queen, noob.",
                "Imagine losing your Queen.",
                "Too easy.",
                "Delete the app.",
                "Where is your lady?",
                "Yoink.",
                "Gimme that.",
                "Bye bye.",
                "You are finished.",
                "Rage quit now.",
                "OMG you are so bad.",
                "Queen down.",
                "Thanks.",
                "Gift accepted.",
                "Lol."
            ]
        },
        
        "Assassin": {
            "blunder": [
                "A fatal mistake. The execution is imminent.",
                "You just hung your king.",
                "Blood in the water. I see the mate.",
                "You fool. It's already over."
            ],
            "miss": [
                "You missed your only chance to survive.",
                "Hesitation is death on the chessboard.",
                "Too slow. The attack continues."
            ],
            "capture": [
                "One less defender to worry about.",
                "I don't care about material. I care about your king.",
                "Your pieces are just obstacles to be removed."
            ],
            "capture_queen": [
                "Your queen is gone. Your king is next.",
                "Hope vanishes with her.",
                "A devastating loss for you."
            ],
            "castle": [
                "Hiding in the corner won't save you.",
                "I will tear open that castled position.",
                "A temporary shelter before the storm."
            ],
            "promotion": [
                "Another piece to join the slaughter.",
                "There is no escaping this."
            ],
            "filler": [
                "I don't play for positional advantages. I play for mate.",
                "Every move you make tightens the noose.",
                "Resign now and save your dignity.",
                "Your defenses are crumbling.",
                "I see a forced mate in your future."
            ]
        },

        # --- THE HISTORIAN ---
        "Historian": {
            "filler": [
                "This reminds me of Morphy vs Duke of Brunswick.",
                "A classic position from the 19th century.",
                "Steinitz would have played f4 here.",
                "The hypermodern school would disagree with that.",
                "This position occurred in 1924, New York.",
                "Are you familiar with the Romantic Era of chess?",
                "Capablanca would simplify here.",
                "Tal would sacrifice a piece here.",
                "History repeats itself.",
                "The immortal game comes to mind.",
                "Lasker used psychology in positions like this.",
                "Botvinnik would analyze this for hours.",
                "Alekhine's gun formulation is possible.",
                "This resembles the famous game of the century.",
                "The Soviet school of chess emphasized this structure.",
                "Philidor stated that pawns are the soul of chess.",
                "Nimzowitsch wrote about this in 'My System'.",
                "A vintage maneuver.",
                "This is straight out of a textbook.",
                "The classical heritage.",
                "Spassky played this against Fischer.",
                "A move worthy of the old masters.",
                "We are walking in the footsteps of giants.",
                "The ancient game of Chaturanga.",
                "Ruy Lopez de Segura wrote about this in 1561.",
                "Greco analyzed this trap.",
                "Anderssen would have attacked.",
                "Petrosian would have exchanged Queens.",
                "This is the Opera Game all over again.",
                "A timeless struggle."
            ],
            "winning": [
                "A victory worthy of Alekhine.",
                "One for the history books.",
                "Fischer would be proud of this conversion.",
                "The ending is elementary, as Watson would say.",
                "A classic example of the minority attack.",
                "This will be analyzed for generations.",
                "A historic triumph.",
                "Like Napoleon at Austerlitz.",
                "I am playing like Kasparov in his prime.",
                "The endgame technique of Capablanca.",
                "A masterpiece.",
                "This game belongs in a museum.",
                "Writing history.",
                "A legendary performance.",
                "The scholars will study this.",
                "An epoch-making move.",
                "Victory is traditional.",
                "I have studied the classics.",
                "A grandmaster class victory.",
                "History favors the bold."
            ],
            "losing": [
                "I have met my Waterloo.",
                "Even Napoleon lost eventually.",
                "A tragic defeat.",
                "History will forget this game.",
                "You played like Deep Blue.",
                "The fall of Rome.",
                "A dark day for history.",
                "I am like Troy, falling.",
                "A historical blunder.",
                "You have rewritten the books.",
                "I concede to the new generation.",
                "My reign is over.",
                "The dynasty ends here.",
                "A revolution on the board.",
                "I am resigned to the annals of history.",
                "The old guard falls.",
                "A bitter pill.",
                "Even Homer nods.",
                "I have been bested by modernity.",
                "Alas."
            ],
            "blunder": [
                "A blunder of historic proportions.",
                "I pulled a funny... like Kramnik vs Deep Fritz.",
                "A historical inaccuracy.",
                "That move belongs in the trash heap of history.",
                "A tragedy.",
                "I forgot my history.",
                "Anachronistic error.",
                "That was not in the books.",
                "A revisionist mistake.",
                "I tarnished my legacy.",
                "Oops, a historical anomaly.",
                "That will be infamous.",
                "A blunder for the ages.",
                "I deviated from the text.",
                "History will judge me."
            ],
            "check": [
                "The King is held at bay.",
                "A royal check.",
                "The monarch is threatened.",
                "Check to the crown.",
                "The sovereign is in danger.",
                "A royal decree: Move!",
                "The King is besieged.",
                "Defend the throne.",
                "A challenge to the King.",
                "Regicide is on my mind."
            ],
            "capture": [
                "Material is seized.",
                "The battlefield clears.",
                "A piece enters the history books.",
                "Casualty of war.",
                "The ranks thin.",
                "A historic capture.",
                "Removing the piece.",
                "The balance shifts.",
                "Claiming the spoils.",
                "War is costly."
            ]
        }
    }
}

# =============================================================================
#  CHAT ENGINE LOGIC (UNCHANGED)
# =============================================================================

import random

class ChatEngine:
    def __init__(self):
        # Memory to prevent repeating lines
        self.speech_memory = {}
        # Trackers for the pacing system
        self.move_counters = {}
        self.chat_targets = {}
        # --- NEW: Opening Memory to prevent spam ---
        self.last_spoken_opening = {}

    def get_style_category(self, style_str):
        if not style_str: return "Default"
        s = style_str.lower()
        if "blunder" in s or "beginner" in s or "learner" in s: return "Blunder Master"
        if "aggressive" in s or "attack" in s: return "Aggressive"
        if "passive" in s or "safe" in s or "defensive" in s: return "Passive"
        if "savage" in s or "toxic" in s or "trash" in s: return "Trash Talker"
        if "history" in s or "old" in s: return "Historian"
        if "tactical" in s or "assassin" in s or "mate" in s: return "Assassin"
        if "grandmaster" in s or "gm" in s or "master" in s or "god" in s: return "GM"
        return "Default"

    def _get_choice(self, options, bot_name="System"):
        if not options: return None
        if bot_name not in self.speech_memory: self.speech_memory[bot_name] = []
            
        bot_memory = self.speech_memory[bot_name]
        memory_limit = min(len(options) // 2, 20)
        recent_lines = bot_memory[-memory_limit:] if memory_limit > 0 else []
        
        available_lines = [line for line in options if line not in recent_lines]
        choice = random.choice(available_lines) if available_lines else random.choice(options)
            
        bot_memory.append(choice)
        if len(bot_memory) > 50: bot_memory.pop(0)
            
        return choice

    def get_response(self, context):
        style = self.get_style_category(context.get("style", ""))
        event = context.get("event")
        opening = context.get("opening")
        eval_state = context.get("eval_state")
        bot_name = context.get("bot_name", style)
        
        allow_idle = context.get("allow_idle", False) 

        style_dict = GAME_DATA.get("styles", {}).get(style, {})
        
        # =========================================================
        # PRIORITY 1: TACTICAL EVENTS
        # =========================================================
        if event and event != "move":
            if "events" in style_dict and event in style_dict["events"]:
                return self._get_choice(style_dict["events"][event], bot_name)
            elif event in GAME_DATA.get("events", {}):
                return self._get_choice(GAME_DATA["events"][event], bot_name)

        # =========================================================
        # PRIORITY 2: OPENING THEORY (Intelligent Anti-Spam)
        # =========================================================
        # It bypasses the gatekeeper, but ONLY if the opening name is new!
        if opening and self.last_spoken_opening.get(bot_name) != opening:
            self.last_spoken_opening[bot_name] = opening
            if "openings" in style_dict and opening in style_dict["openings"]:
                return self._get_choice(style_dict["openings"][opening], bot_name)
            elif opening in GAME_DATA.get("openings", {}):
                return self._get_choice(GAME_DATA["openings"][opening], bot_name)

        # =========================================================
        # THE GATEKEEPER
        # =========================================================
        if not allow_idle:
            return None

        # =========================================================
        # PRIORITY 3: EVALUATION SHIFTS
        # =========================================================
        if eval_state:
            if "eval" in style_dict and eval_state in style_dict["eval"]:
                return self._get_choice(style_dict["eval"][eval_state], bot_name)
            elif eval_state in GAME_DATA.get("eval", {}):
                return self._get_choice(GAME_DATA["eval"][eval_state], bot_name)

        # =========================================================
        # PRIORITY 4: IDLE FILLER
        # =========================================================
        quotes = GAME_DATA.get("quotes", [])
        style_filler = style_dict.get("filler", [])
        trash_filler = GAME_DATA.get("styles", {}).get("Trash Talker", {}).get("filler", [])
        history_filler = GAME_DATA.get("styles", {}).get("Historian", {}).get("filler", [])
        
        female_styles = ["Passive", "Historian"]
        is_female = style in female_styles
        
        roll = random.random()
        
        if roll < 0.10 and quotes: return self._get_choice(quotes, bot_name)
        elif roll < 0.25: 
            if is_female and history_filler: return self._get_choice(history_filler, bot_name)
            elif not is_female and trash_filler: return self._get_choice(trash_filler, bot_name)
        elif style_filler:
            return self._get_choice(style_filler, bot_name)

        return None

# Global Instance
_ENGINE = ChatEngine()

def get_bot_chat(context_data):
    """
    Wrapper for external calls that handles the new Pacing Timer.
    """
    bot_name = context_data.get("bot_name", "System")
    
    # Initialize timers for new bots
    if bot_name not in _ENGINE.move_counters:
        _ENGINE.move_counters[bot_name] = 0
        # --- FIX 1: Set the initial target to 1 so the bot speaks immediately ---
        _ENGINE.chat_targets[bot_name] = 1 
        
    # 1. Count this move
    _ENGINE.move_counters[bot_name] += 1
    
    # 2. Tell the brain if it is allowed to use Idle Filler this turn
    target = _ENGINE.chat_targets[bot_name]
    context_data["allow_idle"] = _ENGINE.move_counters[bot_name] >= target
    
    # 3. Ask the brain for a line
    response = _ENGINE.get_response(context_data)
    
    # 4. If the bot actually spoke (either a Tactic or Idle Filler), reset the timer!
    if response:
        _ENGINE.move_counters[bot_name] = 0
        # --- FIX 2: Set the next random interval to 3-6 moves ---
        _ENGINE.chat_targets[bot_name] = random.randint(3, 6) 
        
    return response