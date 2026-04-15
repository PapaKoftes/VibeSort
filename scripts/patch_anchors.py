"""
patch_anchors.py
Expands thin mood anchors and adds 23 new moods to mood_anchors.json.
"""

import json
import os

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "mood_anchors.json")

# ---------------------------------------------------------------------------
# TASK 1 – extensions for the 57 thin moods
# Keys MUST match the exact mood name already in the JSON.
# ---------------------------------------------------------------------------

EXTENSIONS = {

    # ── 7 anchors → need 5+ more ────────────────────────────────────────────

    "Anime Openings": [
        {"artist": "Yui", "title": "Again"},
        {"artist": "Man with a Mission", "title": "Database"},
        {"artist": "Kana-Boon", "title": "Silhouette"},
        {"artist": "Burnout Syndromes", "title": "火炎"},
        {"artist": "Hiroyuki Sawano", "title": "aLIEz"},
        {"artist": "Myth & Roid", "title": "VORACITY"},
    ],

    "Healing Kind": [
        {"artist": "Daughter", "title": "Youth"},
        {"artist": "Sigur Rós", "title": "Ára bátur"},
        {"artist": "Novo Amor", "title": "Anchor"},
        {"artist": "Bibio", "title": "Lover's Carvings"},
        {"artist": "Peter Gabriel", "title": "In Your Eyes"},
        {"artist": "Big Thief", "title": "Not"},
    ],

    "Shoegaze Breakups": [
        {"artist": "Pale Saints", "title": "Sight of You"},
        {"artist": "Chapterhouse", "title": "Pearl"},
        {"artist": "Nothing", "title": "Dig"},
        {"artist": "Whirr", "title": "Drain"},
        {"artist": "Ringo Deathstarr", "title": "Kaleidoscope"},
        {"artist": "Slowdive", "title": "Dagger"},
    ],

    "Soft Hours": [
        {"artist": "Frank Ocean", "title": "Seigfried"},
        {"artist": "Daniel Caesar", "title": "Best Part"},
        {"artist": "SZA", "title": "Garden (Say It Like Dat)"},
        {"artist": "Sade", "title": "By Your Side"},
        {"artist": "Brent Faiyaz", "title": "Waste My Time"},
        {"artist": "Lucky Daye", "title": "Roll Some Mo"},
    ],

    "Sundown": [
        {"artist": "Khruangbin", "title": "Time (You and I)"},
        {"artist": "Mac DeMarco", "title": "Salad Days"},
        {"artist": "Vampire Weekend", "title": "Hannah Hunt"},
        {"artist": "Bob Dylan", "title": "Knockin' on Heaven's Door"},
        {"artist": "Harry Styles", "title": "Watermelon Sugar"},
        {"artist": "Cat Stevens", "title": "Wild World"},
    ],

    "Synthwave Nights": [
        {"artist": "Lazerhawk", "title": "Overdrive"},
        {"artist": "Dynatron", "title": "Aether"},
        {"artist": "Waveshaper", "title": "The Corporation"},
        {"artist": "Makeup and Vanity Set", "title": "Wilderness"},
        {"artist": "Trevor Something", "title": "Does It Feel Good?"},
        {"artist": "Miami Nights 1984", "title": "Ocean Drive"},
    ],

    # ── 8 anchors → need 4+ more ────────────────────────────────────────────

    "Amapiano Sunset": [
        {"artist": "Kabza De Small", "title": "Amapiano"},
        {"artist": "Young Stunna", "title": "Adiwele"},
        {"artist": "Shakes & Les", "title": "Ngeke Balunge"},
        {"artist": "Daliwonga", "title": "Vele Wena"},
        {"artist": "Vigro Deep", "title": "Baby Boy"},
    ],

    "Classical Calm": [
        {"artist": "Antonio Vivaldi", "title": "The Four Seasons: Spring"},
        {"artist": "Wolfgang Amadeus Mozart", "title": "Piano Sonata No. 11 in A Major"},
        {"artist": "Johann Sebastian Bach", "title": "Goldberg Variations: Aria"},
        {"artist": "Ludovico Einaudi", "title": "Nuvole Bianche"},
        {"artist": "Arvo Pärt", "title": "Spiegel im Spiegel"},
    ],

    "Country Roads": [
        {"artist": "Waylon Jennings", "title": "Mammas Don't Let Your Babies Grow Up to Be Cowboys"},
        {"artist": "Conway Twitty", "title": "Hello Darlin'"},
        {"artist": "Emmylou Harris", "title": "Boulder to Birmingham"},
        {"artist": "Johnny Cash", "title": "Jackson"},
        {"artist": "Kacey Musgraves", "title": "Merry Go 'Round"},
    ],

    "Goth / Darkwave": [
        {"artist": "Christian Death", "title": "Deathwish"},
        {"artist": "Fields of the Nephilim", "title": "Moonchild"},
        {"artist": "Lebanon Hanover", "title": "Gallowdance"},
        {"artist": "Lebanon Hanover", "title": "Your Ways"},
        {"artist": "Boy Harsher", "title": "Pain"},
    ],

    "Indie Bedroom": [
        {"artist": "Frankie Cosmos", "title": "Fool"},
        {"artist": "Soccer Mommy", "title": "Your Dog"},
        {"artist": "Snail Mail", "title": "Heat Wave"},
        {"artist": "Hovvdy", "title": "Brave"},
        {"artist": "Lomelda", "title": "Bam Sha Klam"},
    ],

    "Jazz Nights": [
        {"artist": "Herbie Hancock", "title": "Maiden Voyage"},
        {"artist": "Chet Baker", "title": "My Funny Valentine"},
        {"artist": "Wes Montgomery", "title": "Four on Six"},
        {"artist": "Sonny Rollins", "title": "St. Thomas"},
        {"artist": "Oscar Peterson", "title": "Night Train"},
    ],

    "Kawaii Metal Sparkle": [
        {"artist": "BABYMETAL", "title": "The One"},
        {"artist": "BABYMETAL", "title": "Distortion"},
        {"artist": "Necronomidol", "title": "Ithaqua"},
        {"artist": "PassCode", "title": "Tonight"},
        {"artist": "Fruitpochette", "title": "Shitsuren Sensation"},
    ],

    "Latin Ballroom Heat": [
        {"artist": "Willie Colon", "title": "Idilio"},
        {"artist": "Hector Lavoe", "title": "El Cantante"},
        {"artist": "Johnny Pacheco", "title": "Acuyuye"},
        {"artist": "La India", "title": "Ese Hombre"},
        {"artist": "Celia Cruz", "title": "Quimbara"},
    ],

    "Latin Heat": [
        {"artist": "Karol G", "title": "PROVENZA"},
        {"artist": "Anuel AA", "title": "China"},
        {"artist": "Rauw Alejandro", "title": "Todo de Ti"},
        {"artist": "CNCO", "title": "Reggaeton Lento (Remix)"},
        {"artist": "Bad Bunny", "title": "MIA"},
    ],

    "Metal Testimony": [
        {"artist": "Underoath", "title": "Writing on the Walls"},
        {"artist": "As I Lay Dying", "title": "A Greater Foundation"},
        {"artist": "Norma Jean", "title": "Memphis Will Be Laid to Waste"},
        {"artist": "The Devil Wears Prada", "title": "HTML Rulez D00d"},
        {"artist": "Anberlin", "title": "Feel Good Drag"},
    ],

    "Weightless": [
        {"artist": "Hammock", "title": "Breathturn"},
        {"artist": "Tim Hecker", "title": "In the Fog I"},
        {"artist": "Stars of the Lid", "title": "Dungtitled (In A Major)"},
        {"artist": "Colleen", "title": "Summer Water"},
        {"artist": "Johann Johannsson", "title": "The Sun's Gone Dim"},
    ],

    # ── 9 anchors → need 3+ more ────────────────────────────────────────────

    "Anime Endings": [
        {"artist": "Wada Kouji", "title": "Butter-Fly"},
        {"artist": "Sheena Easton", "title": "For Your Eyes Only"},
        {"artist": "EGOIST", "title": "departures ~あなたにおくるアイの歌~"},
        {"artist": "Amazarashi", "title": "Yuuzora Trumpet"},
        {"artist": "Kenshi Yonezu", "title": "Peace Sign"},
    ],

    "Baroque Pop Melodrama": [
        {"artist": "The Divine Comedy", "title": "National Express"},
        {"artist": "Rufus Wainwright", "title": "Cigarettes and Chocolate Milk"},
        {"artist": "Nellie McKay", "title": "David"},
        {"artist": "Patrick Wolf", "title": "The Magic Position"},
        {"artist": "Elbow", "title": "One Day Like This"},
    ],

    "Cloud Rap Haze": [
        {"artist": "Ethereal", "title": "Sacrifice"},
        {"artist": "Key!", "title": "Break"},
        {"artist": "Main Attrakionz", "title": "800xl"},
        {"artist": "Spaceghostpurrp", "title": "Bringing It Back"},
        {"artist": "Father", "title": "Look at Wrist"},
    ],

    "Disco Lights": [
        {"artist": "Michael Jackson", "title": "Don't Stop 'Til You Get Enough"},
        {"artist": "Donna Summer", "title": "Last Dance"},
        {"artist": "Earth, Wind & Fire", "title": "September"},
        {"artist": "Kool & the Gang", "title": "Get Down on It"},
        {"artist": "Diana Ross", "title": "I'm Coming Out"},
    ],

    "Dream Pop Haze": [
        {"artist": "Alvvays", "title": "Archie, Marry Me"},
        {"artist": "Men I Trust", "title": "Tailwhip"},
        {"artist": "Weyes Blood", "title": "Andromeda"},
        {"artist": "Still Woozy", "title": "Lava"},
        {"artist": "Japanese Breakfast", "title": "Everybody Wants to Love You"},
    ],

    "Drill": [
        {"artist": "Lil Durk", "title": "The Voice"},
        {"artist": "G Herbo", "title": "PTSD"},
        {"artist": "Polo G", "title": "Pop Out"},
        {"artist": "Luciano", "title": "Cómo"},
        {"artist": "Meekz", "title": "Respect the Connect"},
    ],

    "Drill Confessions": [
        {"artist": "Lil Durk", "title": "India"},
        {"artist": "Sleepy Hallow", "title": "2055"},
        {"artist": "Sheff G", "title": "No Suburban"},
        {"artist": "22Gz", "title": "Suburban"},
        {"artist": "Dtheflyest", "title": "Love & War"},
    ],

    "Emo Hour": [
        {"artist": "The Used", "title": "The Taste of Ink"},
        {"artist": "Hawthorne Heights", "title": "Ohio Is for Lovers"},
        {"artist": "Story of the Year", "title": "Until the Day I Die"},
        {"artist": "Senses Fail", "title": "Lady in a Blue Dress"},
        {"artist": "Thursday", "title": "Understanding in a Car Crash"},
    ],

    "Flex Tape": [
        {"artist": "Roddy Ricch", "title": "The Box"},
        {"artist": "DaBaby", "title": "ROCKSTAR"},
        {"artist": "Polo G", "title": "RAPSTAR"},
        {"artist": "Lil Durk", "title": "Broadway Girls"},
        {"artist": "42 Dugg", "title": "4 Da Gang"},
    ],

    "Gospel Fire": [
        {"artist": "Andraé Crouch", "title": "Through It All"},
        {"artist": "CeCe Winans", "title": "Goodness of God"},
        {"artist": "Tamela Mann", "title": "Take Me to the King"},
        {"artist": "Marvin Sapp", "title": "Never Would Have Made It"},
        {"artist": "Donnie McClurkin", "title": "Stand"},
    ],

    "Industrial Gothic Floor": [
        {"artist": "Skinny Puppy", "title": "Assimilate"},
        {"artist": "Einstürzende Neubauten", "title": "Sabrina"},
        {"artist": "Covenant", "title": "Like Tears in Rain"},
        {"artist": "VNV Nation", "title": "Epicentre"},
        {"artist": "Combichrist", "title": "What the F**k Is Wrong with You?"},
    ],

    "J-Metal": [
        {"artist": "One OK Rock", "title": "Wherever You Are"},
        {"artist": "Coldrain", "title": "Envy"},
        {"artist": "SiM", "title": "Blah Blah Blah"},
        {"artist": "Pay Money To My Pain", "title": "Pictures"},
        {"artist": "lynch.", "title": "EVOKE"},
    ],

    "J-Pop": [
        {"artist": "Kenshi Yonezu", "title": "Paprika"},
        {"artist": "King Gnu", "title": "白日"},
        {"artist": "Fujii Kaze", "title": "Matsuri"},
        {"artist": "YOASOBI", "title": "夜に駆ける"},
        {"artist": "Ado", "title": "Gira Gira"},
    ],

    "Midnight Clarity": [
        {"artist": "James Blake", "title": "Retrograde"},
        {"artist": "Tyler, the Creator", "title": "See You Again"},
        {"artist": "Sampha", "title": "Process"},
        {"artist": "Bon Iver", "title": "re: Stacks"},
        {"artist": "Nick Drake", "title": "Northern Sky"},
    ],

    "Minimal Techno Tunnel": [
        {"artist": "Speedy J", "title": "De-Orbit"},
        {"artist": "Monolake", "title": "Cyan"},
        {"artist": "Cio D'Or", "title": "Inizio"},
        {"artist": "Markus Suckut", "title": "Kaya"},
        {"artist": "Regis", "title": "Gymnast"},
    ],

    "Money Talks": [
        {"artist": "Kendrick Lamar", "title": "Money Trees"},
        {"artist": "Travis Scott", "title": "Antidote"},
        {"artist": "Future", "title": "Bugatti"},
        {"artist": "Gunna", "title": "Dollaz on My Head"},
        {"artist": "Lil Baby", "title": "Sum 2 Prove"},
    ],

    "Neo-Soul": [
        {"artist": "Musiq Soulchild", "title": "Just Friends (Sunny)"},
        {"artist": "H.E.R.", "title": "Focus"},
        {"artist": "Lucky Daye", "title": "Real Games"},
        {"artist": "SZA", "title": "Good Days"},
        {"artist": "Brent Faiyaz", "title": "Dead Man Walking"},
    ],

    "Open Road": [
        {"artist": "Simon & Garfunkel", "title": "America"},
        {"artist": "Lynyrd Skynyrd", "title": "Free Bird"},
        {"artist": "John Denver", "title": "Rocky Mountain High"},
        {"artist": "Chris Stapleton", "title": "Broken Halos"},
        {"artist": "James McMurtry", "title": "We Can't Make It Here"},
    ],

    "Phonk Season": [
        {"artist": "Sickboyrari", "title": "Faygo Dreams"},
        {"artist": "DJ Smokey", "title": "Caught in the Rain"},
        {"artist": "$uicideboy$", "title": "Paris"},
        {"artist": "City Morgue", "title": "Shinners 13"},
        {"artist": "Interworld", "title": "Metamorphosis"},
    ],

    "Psychedelic": [
        {"artist": "King Gizzard and the Lizard Wizard", "title": "Rattlesnake"},
        {"artist": "Pond", "title": "Waiting Around"},
        {"artist": "Unknown Mortal Orchestra", "title": "Multi-Love"},
        {"artist": "Ty Segall", "title": "Feel"},
        {"artist": "Allah-Las", "title": "Catamaran"},
    ],

    "Punk Sprint": [
        {"artist": "Descendents", "title": "Suburban Home"},
        {"artist": "The Misfits", "title": "Last Caress"},
        {"artist": "Pennywise", "title": "Bro Hymn"},
        {"artist": "Circle Jerks", "title": "Wild in the Streets"},
        {"artist": "Dead Kennedys", "title": "Holiday in Cambodia"},
    ],

    "Queer Dance Confetti": [
        {"artist": "Carly Rae Jepsen", "title": "Run Away with Me"},
        {"artist": "Kim Petras", "title": "Coconuts"},
        {"artist": "Robyn", "title": "Dancing On My Own"},
        {"artist": "Rufus Wainwright", "title": "Gay Messiah"},
        {"artist": "Slayyyter", "title": "Mine"},
    ],

    "Sea Shanty Singalong": [
        {"artist": "The Longest Johns", "title": "The Grey Selkie"},
        {"artist": "Fisherman's Friends", "title": "Little Liza Jane"},
        {"artist": "Great Big Sea", "title": "Fast as I Can"},
        {"artist": "Kimber's Men", "title": "Haul on the Bowline"},
        {"artist": "The Dreadnoughts", "title": "Polka Never Dies"},
    ],

    "Slow Jams": [
        {"artist": "Al Green", "title": "Let's Stay Together"},
        {"artist": "Luther Vandross", "title": "Never Too Much"},
        {"artist": "Silk", "title": "Freak Me"},
        {"artist": "Marvin Gaye", "title": "Let's Get It On"},
        {"artist": "Sade", "title": "No Ordinary Love"},
    ],

    "Smoke & Mirrors": [
        {"artist": "Portishead", "title": "Sour Times"},
        {"artist": "Tricky", "title": "Black Steel"},
        {"artist": "Massive Attack", "title": "Teardrop"},
        {"artist": "Unkle", "title": "Rabbit in Your Headlights"},
        {"artist": "Bonobo", "title": "Kong"},
    ],

    "Songs About Goodbye": [
        {"artist": "The Postal Service", "title": "Such Great Heights"},
        {"artist": "The Fray", "title": "How to Save a Life"},
        {"artist": "Snow Patrol", "title": "Run"},
        {"artist": "Passenger", "title": "Let Her Go"},
        {"artist": "James Blunt", "title": "Goodbye My Lover"},
    ],

    "Sunday Reset": [
        {"artist": "Bon Iver", "title": "Skinny Love"},
        {"artist": "Villagers", "title": "Becoming a Jackal"},
        {"artist": "Fleet Foxes", "title": "Mykonos"},
        {"artist": "Andrew Bird", "title": "Armchairs"},
        {"artist": "Gregory Alan Isakov", "title": "The Stable Song"},
    ],

    "Symphonic Metal Epics": [
        {"artist": "Delain", "title": "Stardust"},
        {"artist": "Kamelot", "title": "The Haunting"},
        {"artist": "Xandria", "title": "Call of Destiny"},
        {"artist": "Nightwish", "title": "Nemo"},
        {"artist": "Lacuna Coil", "title": "Heaven's a Lie"},
    ],

    "Vaporwave": [
        {"artist": "Luxury Elite", "title": "World Class"},
        {"artist": "猫 シ Corp.", "title": "Palm Mall"},
        {"artist": "Hiraeth", "title": "Chill with Me"},
        {"artist": "VAPERROR", "title": "Mango Sunrise"},
        {"artist": "Telepath テレパシー能力者", "title": "Love"},
    ],

    "Warehouse Techno": [
        {"artist": "Marcel Dettmann", "title": "Lenia"},
        {"artist": "Blawan", "title": "Getting Me Down"},
        {"artist": "Rebekah", "title": "Concrete"},
        {"artist": "Phase Fatale", "title": "Alcatraz"},
        {"artist": "Paula Temple", "title": "Edge of Everything"},
    ],

    # ── 10 anchors → need 2+ more ────────────────────────────────────────────

    "3 AM Unsent Texts": [
        {"artist": "Phoebe Bridgers", "title": "Garden Song"},
        {"artist": "Sufjan Stevens", "title": "Should Have Known Better"},
        {"artist": "Elliott Smith", "title": "Say Yes"},
    ],

    "Acoustic Corner": [
        {"artist": "Cat Stevens", "title": "Wild World"},
        {"artist": "John Denver", "title": "Annie's Song"},
        {"artist": "Simon & Garfunkel", "title": "The Sound of Silence"},
    ],

    "Adrenaline": [
        {"artist": "Deftones", "title": "My Own Summer (Shove It)"},
        {"artist": "Korn", "title": "Freak on a Leash"},
        {"artist": "Disturbed", "title": "Down with the Sickness"},
    ],

    "Afro-Fusion Golden Hour": [
        {"artist": "Tiwa Savage", "title": "Somebody's Son"},
        {"artist": "Kizz Daniel", "title": "Buga"},
        {"artist": "Oxlade", "title": "Ku Lo Sa"},
    ],

    "Afterparty": [
        {"artist": "Dua Lipa", "title": "Levitating"},
        {"artist": "The Weeknd", "title": "Blinding Lights"},
        {"artist": "Doja Cat", "title": "Say So"},
    ],

    "Anime OST Energy": [
        {"artist": "Yoko Kanno", "title": "Rise"},
        {"artist": "Hiroyuki Sawano", "title": "e·vil"},
        {"artist": "Masashi Hamauzu", "title": "Defiers of Fate"},
    ],

    "Anti-Hero Receipts": [
        {"artist": "Childish Gambino", "title": "This Is America"},
        {"artist": "Tyler, the Creator", "title": "EARFQUAKE"},
        {"artist": "21 Savage", "title": "a lot"},
    ],

    "Bedroom Pop Diary": [
        {"artist": "girl in red", "title": "we fell in love in october"},
        {"artist": "beabadoobee", "title": "Care"},
        {"artist": "Chloe Moriondo", "title": "Fruity"},
    ],

    "Brass & Drumline Energy": [
        {"artist": "Trombone Shorty", "title": "Hurricane Season"},
        {"artist": "Vulfpeck", "title": "Dean Town"},
        {"artist": "Lucky Chops", "title": "Souvenir"},
    ],

    "Chillhop Cafe": [
        {"artist": "Kupla", "title": "Flowers"},
        {"artist": "Saib.", "title": "Sunday Afternoon"},
        {"artist": "Mondo Loops", "title": "Beignet"},
    ],

    "Country Story Hour": [
        {"artist": "John Prine", "title": "Angel from Montgomery"},
        {"artist": "Townes Van Zandt", "title": "If I Needed You"},
        {"artist": "Blaze Foley", "title": "If I Could Only Fly"},
    ],

    "Dark Pop": [
        {"artist": "Doja Cat", "title": "Streets"},
        {"artist": "Charli XCX", "title": "Gone"},
        {"artist": "Rina Sawayama", "title": "STFU!"},
    ],

    "Deep Focus": [
        {"artist": "Bonobo", "title": "Kong"},
        {"artist": "Floating Points", "title": "LesAlpx"},
        {"artist": "Jon Hopkins", "title": "Immunity"},
    ],

    "Euphoric Rave": [
        {"artist": "Paul van Dyk", "title": "For an Angel"},
        {"artist": "ATB", "title": "9 PM (Till I Come)"},
        {"artist": "Infected Mushroom", "title": "Converting Vegetarians"},
    ],

    "Golden Hour": [
        {"artist": "Jack Johnson", "title": "Better Together"},
        {"artist": "Jason Mraz", "title": "I'm Yours"},
        {"artist": "Ben Harper", "title": "Steal My Kisses"},
    ],

    "Hard Reset": [
        {"artist": "Nine Inch Nails", "title": "The Hand That Feeds"},
        {"artist": "Rage Against the Machine", "title": "Killing in the Name"},
        {"artist": "Audioslave", "title": "Like a Stone"},
    ],

    "Heartbreak": [
        {"artist": "Jhené Aiko", "title": "Comfort Inn Ending?"},
        {"artist": "Giveon", "title": "Heartbreak Anniversary"},
        {"artist": "SZA", "title": "Good Days"},
    ],

    "Hollow": [
        {"artist": "James Blake", "title": "Limit to Your Love"},
        {"artist": "Daughter", "title": "Youth"},
        {"artist": "Mount Eerie", "title": "Real Death"},
    ],

    "Hyperpop": [
        {"artist": "Arca", "title": "Nonbinary"},
        {"artist": "Fraxiom", "title": "Thos Moser"},
        {"artist": "Umru", "title": "Broken xoxo"},
    ],

    "Hyperpop Emotional Crash": [
        {"artist": "Bladee", "title": "Spiderr"},
        {"artist": "Lil Tracy", "title": "Like a Rage"},
        {"artist": "Ethereal", "title": "Sacrifice"},
    ],

    "K-Pop Zone": [
        {"artist": "NewJeans", "title": "Hype Boy"},
        {"artist": "LE SSERAFIM", "title": "FEARLESS"},
        {"artist": "TXT", "title": "0X1=LOVESONG"},
    ],

    "Late Night Drive": [
        {"artist": "Tycho", "title": "Awake"},
        {"artist": "Bonobo", "title": "Kiara"},
        {"artist": "Nightcrawlers", "title": "Push the Feeling On"},
    ],

    "Liminal": [
        {"artist": "Johann Johannsson", "title": "The Sun's Gone Dim"},
        {"artist": "Hammock", "title": "Breathturn"},
        {"artist": "Ólafur Arnalds", "title": "Near Light"},
    ],

    "Lo-Fi Flow": [
        {"artist": "Saib.", "title": "Sunday Afternoon"},
        {"artist": "Knxwledge", "title": "Remind Me"},
        {"artist": "knxwledge", "title": "HW2Flrt"},
    ],

    "Meditation Bath": [
        {"artist": "Ólafur Arnalds", "title": "Near Light"},
        {"artist": "Biosphere", "title": "Substrata"},
        {"artist": "Lycia", "title": "Walk"},
    ],

    "Metal Storm": [
        {"artist": "Cannibal Corpse", "title": "Hammer Smashed Face"},
        {"artist": "Behemoth", "title": "Ov Fire and the Void"},
        {"artist": "Cattle Decapitation", "title": "Bring Back the Plague"},
    ],

    "Morning Ritual": [
        {"artist": "Feist", "title": "1234"},
        {"artist": "Vampire Weekend", "title": "Hannah Hunt"},
        {"artist": "The Shins", "title": "New Slang"},
    ],

    "Nostalgia": [
        {"artist": "Bruce Springsteen", "title": "Glory Days"},
        {"artist": "Tom Petty", "title": "Free Fallin'"},
        {"artist": "R.E.M.", "title": "Everybody Hurts"},
    ],

    "Old School Hip-Hop": [
        {"artist": "Slick Rick", "title": "Children's Story"},
        {"artist": "Eric B. & Rakim", "title": "Paid in Full"},
        {"artist": "Big Daddy Kane", "title": "Ain't No Half-Steppin'"},
    ],

    "Overflow": [
        {"artist": "Mitski", "title": "Your Best American Girl"},
        {"artist": "Phoebe Bridgers", "title": "Funeral"},
        {"artist": "Daughter", "title": "Candles"},
    ],

    "Overthinking": [
        {"artist": "Faye Webster", "title": "Room Temperature"},
        {"artist": "Clairo", "title": "Sling"},
        {"artist": "Soccer Mommy", "title": "Circle the Drain"},
    ],

    "Pluggnb Heartache": [
        {"artist": "Yung Bleu", "title": "You're Mines Still"},
        {"artist": "Toosii", "title": "Thank You For Everything"},
        {"artist": "Lil Durk", "title": "What Happened to Virgil"},
    ],

    "Rage Lift": [
        {"artist": "Metallica", "title": "Battery"},
        {"artist": "Slayer", "title": "Raining Blood"},
        {"artist": "Gojira", "title": "Backbone"},
    ],

    "Rainy Window": [
        {"artist": "Daughter", "title": "Landfill"},
        {"artist": "Novo Amor", "title": "Carry You"},
        {"artist": "Cigarettes After Sex", "title": "Sunsetz"},
    ],

    "Raw Emotion": [
        {"artist": "Phoebe Bridgers", "title": "Funeral"},
        {"artist": "Jeff Buckley", "title": "Lover, You Should've Come Over"},
        {"artist": "Mitski", "title": "Your Best American Girl"},
    ],

    "Runaway Highways": [
        {"artist": "Allman Brothers Band", "title": "Ramblin' Man"},
        {"artist": "The Marshall Tucker Band", "title": "Can't You See"},
        {"artist": "ZZ Top", "title": "Sharp Dressed Man"},
    ],

    "Same Vibe Different Genre": [
        {"artist": "LCD Soundsystem", "title": "All My Friends"},
        {"artist": "Hot Chip", "title": "Ready for the Floor"},
        {"artist": "Gorillaz", "title": "On Melancholy Hill"},
    ],

    "Songs About Home": [
        {"artist": "James Taylor", "title": "Carolina in My Mind"},
        {"artist": "Paul Simon", "title": "Graceland"},
        {"artist": "The National", "title": "Bloodbuzz Ohio"},
    ],

    "Tropicana": [
        {"artist": "Kali Uchis", "title": "Telepatia"},
        {"artist": "Karol G", "title": "Tusa"},
        {"artist": "Fireboy DML", "title": "Peru (Remix)"},
    ],

    "Villain Arc": [
        {"artist": "Kanye West", "title": "POWER"},
        {"artist": "Kendrick Lamar", "title": "King Kunta"},
        {"artist": "Drake", "title": "Forever"},
    ],
}

# ---------------------------------------------------------------------------
# TASK 2 – 23 brand-new moods (8-10 anchors each)
# ---------------------------------------------------------------------------

NEW_MOODS = {

    "Cinematic Swell": [
        {"artist": "Hans Zimmer", "title": "Time"},
        {"artist": "Hans Zimmer", "title": "Why So Serious?"},
        {"artist": "John Williams", "title": "Duel of the Fates"},
        {"artist": "John Williams", "title": "The Imperial March"},
        {"artist": "Ennio Morricone", "title": "The Ecstasy of Gold"},
        {"artist": "Howard Shore", "title": "The Breaking of the Fellowship"},
        {"artist": "Max Richter", "title": "On the Nature of Daylight"},
        {"artist": "Thomas Newman", "title": "American Beauty"},
        {"artist": "Jóhann Jóhannsson", "title": "The Beast"},
        {"artist": "Ludovico Einaudi", "title": "Experience"},
    ],

    "Breakup Bravado": [
        {"artist": "Taylor Swift", "title": "We Are Never Ever Getting Back Together"},
        {"artist": "Lizzo", "title": "Good as Hell"},
        {"artist": "Gloria Gaynor", "title": "I Will Survive"},
        {"artist": "Destiny's Child", "title": "Survivor"},
        {"artist": "Ariana Grande", "title": "thank u, next"},
        {"artist": "Dua Lipa", "title": "New Rules"},
        {"artist": "Kelly Clarkson", "title": "Since U Been Gone"},
        {"artist": "Alanis Morissette", "title": "You Oughta Know"},
        {"artist": "Olivia Rodrigo", "title": "good 4 u"},
        {"artist": "Beyoncé", "title": "Irreplaceable"},
    ],

    "Campfire Sessions": [
        {"artist": "Bob Dylan", "title": "Blowin' in the Wind"},
        {"artist": "Joni Mitchell", "title": "The Circle Game"},
        {"artist": "James Taylor", "title": "Fire and Rain"},
        {"artist": "Simon & Garfunkel", "title": "Scarborough Fair"},
        {"artist": "John Denver", "title": "Take Me Home, Country Roads"},
        {"artist": "Fleet Foxes", "title": "White Winter Hymnal"},
        {"artist": "Sufjan Stevens", "title": "Death With Dignity"},
        {"artist": "Iron & Wine", "title": "The Trapeze Swinger"},
        {"artist": "Bon Iver", "title": "Skinny Love"},
        {"artist": "Gregory Alan Isakov", "title": "The Stable Song"},
    ],

    "Running Fuel": [
        {"artist": "Eminem", "title": "Lose Yourself"},
        {"artist": "Kanye West", "title": "Stronger"},
        {"artist": "Survivor", "title": "Eye of the Tiger"},
        {"artist": "The Killers", "title": "Mr. Brightside"},
        {"artist": "AC/DC", "title": "Thunderstruck"},
        {"artist": "Daft Punk", "title": "Harder, Better, Faster, Stronger"},
        {"artist": "Imagine Dragons", "title": "Believer"},
        {"artist": "Twenty One Pilots", "title": "Heathens"},
        {"artist": "Kendrick Lamar", "title": "HUMBLE."},
        {"artist": "Run-D.M.C.", "title": "It's Tricky"},
    ],

    "Grief Wave": [
        {"artist": "Sufjan Stevens", "title": "Death With Dignity"},
        {"artist": "The National", "title": "Sorrow"},
        {"artist": "Nick Cave & The Bad Seeds", "title": "Into My Arms"},
        {"artist": "Mount Eerie", "title": "Real Death"},
        {"artist": "Phoebe Bridgers", "title": "Funeral"},
        {"artist": "Bon Iver", "title": "re: Stacks"},
        {"artist": "Elliott Smith", "title": "Waltz #2 (XO)"},
        {"artist": "Jeff Buckley", "title": "Lover, You Should've Come Over"},
        {"artist": "Weyes Blood", "title": "Movies"},
        {"artist": "Sharon Van Etten", "title": "Every Time the Sun Comes Up"},
    ],

    "Piano Bar": [
        {"artist": "Bill Evans", "title": "Waltz for Debby"},
        {"artist": "Thelonious Monk", "title": "Round Midnight"},
        {"artist": "Oscar Peterson", "title": "Night Train"},
        {"artist": "Erroll Garner", "title": "Misty"},
        {"artist": "Keith Jarrett", "title": "The Köln Concert: Part I"},
        {"artist": "Ahmad Jamal", "title": "Poinciana"},
        {"artist": "Herbie Hancock", "title": "Maiden Voyage"},
        {"artist": "Chick Corea", "title": "Spain"},
        {"artist": "McCoy Tyner", "title": "Search for Peace"},
        {"artist": "Art Tatum", "title": "Tea for Two"},
    ],

    "Trap & Chill": [
        {"artist": "Travis Scott", "title": "Through the Late Night"},
        {"artist": "Young Thug", "title": "Digits"},
        {"artist": "Future", "title": "Codeine Crazy"},
        {"artist": "Lil Uzi Vert", "title": "7AM"},
        {"artist": "Metro Boomin", "title": "Space Cadet"},
        {"artist": "Gunna", "title": "Speed It Up"},
        {"artist": "Playboi Carti", "title": "Magnolia"},
        {"artist": "Lil Baby", "title": "Emotionally Scarred"},
        {"artist": "21 Savage", "title": "Savage Mode"},
        {"artist": "Offset", "title": "Ric Flair Drip"},
    ],

    "Coffee Shop Folk": [
        {"artist": "Damien Rice", "title": "The Blower's Daughter"},
        {"artist": "Iron & Wine", "title": "Naked As We Came"},
        {"artist": "Sufjan Stevens", "title": "Futile Devices"},
        {"artist": "Bon Iver", "title": "Skinny Love"},
        {"artist": "José González", "title": "Heartbeats"},
        {"artist": "Nick Drake", "title": "Pink Moon"},
        {"artist": "Laura Marling", "title": "Rambling Man"},
        {"artist": "Fionn Regan", "title": "Be Good or Be Gone"},
        {"artist": "Passenger", "title": "Let Her Go"},
        {"artist": "Ben Howard", "title": "I Forget Where We Were"},
    ],

    "Boxing Ring": [
        {"artist": "50 Cent", "title": "In da Club"},
        {"artist": "DMX", "title": "X Gon' Give It to Ya"},
        {"artist": "Eminem", "title": "Till I Collapse"},
        {"artist": "Survivor", "title": "Eye of the Tiger"},
        {"artist": "AC/DC", "title": "Back in Black"},
        {"artist": "The White Stripes", "title": "Seven Nation Army"},
        {"artist": "Kanye West", "title": "Power"},
        {"artist": "Kendrick Lamar", "title": "DNA."},
        {"artist": "Run-D.M.C.", "title": "It's Tricky"},
        {"artist": "2Pac", "title": "Ambitionz az a Ridah"},
    ],

    "New City Energy": [
        {"artist": "Vampire Weekend", "title": "A-Punk"},
        {"artist": "LCD Soundsystem", "title": "All My Friends"},
        {"artist": "Arcade Fire", "title": "Ready to Start"},
        {"artist": "Talking Heads", "title": "This Must Be the Place"},
        {"artist": "Phoenix", "title": "1901"},
        {"artist": "The Strokes", "title": "Last Nite"},
        {"artist": "Alvvays", "title": "Archie, Marry Me"},
        {"artist": "Matt and Kim", "title": "Daylight"},
        {"artist": "CSS", "title": "Alala"},
        {"artist": "Friendly Fires", "title": "Paris"},
    ],

    "Acoustic Soul": [
        {"artist": "Tracy Chapman", "title": "Fast Car"},
        {"artist": "John Legend", "title": "Ordinary People"},
        {"artist": "Ben Harper", "title": "Steal My Kisses"},
        {"artist": "Corinne Bailey Rae", "title": "Put Your Records On"},
        {"artist": "India.Arie", "title": "Video"},
        {"artist": "Alicia Keys", "title": "If I Ain't Got You"},
        {"artist": "Musiq Soulchild", "title": "Love"},
        {"artist": "Donny Hathaway", "title": "A Song for You"},
        {"artist": "Erykah Badu", "title": "On & On"},
        {"artist": "D'Angelo", "title": "Brown Sugar"},
    ],

    "Retro Future": [
        {"artist": "A-ha", "title": "Take On Me"},
        {"artist": "Depeche Mode", "title": "Just Can't Get Enough"},
        {"artist": "Gary Numan", "title": "Cars"},
        {"artist": "Talking Heads", "title": "Once in a Lifetime"},
        {"artist": "New Order", "title": "Blue Monday"},
        {"artist": "The Human League", "title": "Don't You Want Me"},
        {"artist": "Tears for Fears", "title": "Everybody Wants to Rule the World"},
        {"artist": "Duran Duran", "title": "Hungry Like the Wolf"},
        {"artist": "Howard Jones", "title": "Things Can Only Get Better"},
        {"artist": "Ultravox", "title": "Vienna"},
    ],

    "Winter Dark": [
        {"artist": "Wardruna", "title": "Helvegen"},
        {"artist": "Heilung", "title": "Krigsgaldr"},
        {"artist": "Myrkur", "title": "Ulvinde"},
        {"artist": "Sigur Rós", "title": "Svefn-g-englar"},
        {"artist": "Ólafur Arnalds", "title": "Near Light"},
        {"artist": "Jóhann Jóhannsson", "title": "The Sun's Gone Dim"},
        {"artist": "Árstíðir", "title": "Heyr himna smiður"},
        {"artist": "Sólstafir", "title": "Ótta"},
        {"artist": "Agalloch", "title": "In the Shadow of Our Pale Companion"},
        {"artist": "Wolves in the Throne Room", "title": "Turning Ever Towards the Sun"},
    ],

    "Protest Songs": [
        {"artist": "Rage Against the Machine", "title": "Killing in the Name"},
        {"artist": "Public Enemy", "title": "Fight the Power"},
        {"artist": "Bob Dylan", "title": "The Times They Are a-Changin'"},
        {"artist": "Billie Holiday", "title": "Strange Fruit"},
        {"artist": "Nina Simone", "title": "Mississippi Goddam"},
        {"artist": "Marvin Gaye", "title": "What's Going On"},
        {"artist": "Bruce Springsteen", "title": "The Ghost of Tom Joad"},
        {"artist": "Tracy Chapman", "title": "Talkin' Bout a Revolution"},
        {"artist": "N.W.A", "title": "F**k tha Police"},
        {"artist": "Kendrick Lamar", "title": "Alright"},
    ],

    "Epic Gaming": [
        {"artist": "Nobuo Uematsu", "title": "One-Winged Angel"},
        {"artist": "Koji Kondo", "title": "Super Mario Bros. Theme"},
        {"artist": "Martin O'Donnell", "title": "Mjolnir Mix"},
        {"artist": "Jeremy Soule", "title": "Dragonborn"},
        {"artist": "Yoko Shimomura", "title": "Dearly Beloved"},
        {"artist": "Yasunori Mitsuda", "title": "To Far Away Times"},
        {"artist": "Mick Gordon", "title": "BFG Division"},
        {"artist": "Darren Korb", "title": "Setting Sail, Coming Home"},
        {"artist": "Inon Zur", "title": "Fallout 4 Main Theme"},
        {"artist": "Jesper Kyd", "title": "Ezio's Family"},
    ],

    "Club Warm-Up": [
        {"artist": "Caribou", "title": "Can't Do Without You"},
        {"artist": "Bicep", "title": "Glue"},
        {"artist": "Four Tet", "title": "Baby"},
        {"artist": "Peggy Gou", "title": "(It Goes Like) Nanana"},
        {"artist": "Fred again..", "title": "Marea (We've Lost Dancing)"},
        {"artist": "Floating Points", "title": "Silhouettes"},
        {"artist": "Joy Orbison", "title": "Hyph Mngo"},
        {"artist": "Shackleton", "title": "Blood on My Hands"},
        {"artist": "Call Super", "title": "Doxa"},
        {"artist": "Denis Sulta", "title": "I'm in a Room"},
    ],

    "Midnight Gospel": [
        {"artist": "King Krule", "title": "Dum Surfer"},
        {"artist": "Swans", "title": "The Seer"},
        {"artist": "Coil", "title": "Ostia (The Death of Pasolini)"},
        {"artist": "Scott Walker", "title": "The Electrician"},
        {"artist": "Nick Cave & The Bad Seeds", "title": "Red Right Hand"},
        {"artist": "Tom Waits", "title": "Tom Traubert's Blues"},
        {"artist": "Leonard Cohen", "title": "Famous Blue Raincoat"},
        {"artist": "Current 93", "title": "I Have a Special Plan for This World"},
        {"artist": "Ween", "title": "The Mollusk"},
        {"artist": "Primus", "title": "Tommy the Cat"},
    ],

    "Work Mode": [
        {"artist": "Daft Punk", "title": "Harder, Better, Faster, Stronger"},
        {"artist": "Bonobo", "title": "Kong"},
        {"artist": "Tycho", "title": "Awake"},
        {"artist": "Röyksopp", "title": "Remind Me"},
        {"artist": "Thievery Corporation", "title": "The Richest Man in Babylon"},
        {"artist": "Amon Tobin", "title": "Esther's"},
        {"artist": "Portishead", "title": "Sour Times"},
        {"artist": "Four Tet", "title": "She Moves She"},
        {"artist": "Aphex Twin", "title": "Xtal"},
        {"artist": "Bonobo", "title": "Kiara"},
    ],

    "Bedroom Confessions": [
        {"artist": "Frank Ocean", "title": "Self Control"},
        {"artist": "Sufjan Stevens", "title": "Futile Devices"},
        {"artist": "Phoebe Bridgers", "title": "Moon Song"},
        {"artist": "Julien Baker", "title": "Rejoice"},
        {"artist": "Angel Olsen", "title": "Shut Up Kiss Me"},
        {"artist": "Adrianne Lenker", "title": "anything"},
        {"artist": "Lucy Dacus", "title": "Night Shift"},
        {"artist": "Mitski", "title": "I Don't Smoke"},
        {"artist": "Snail Mail", "title": "Pristine"},
        {"artist": "boygenius", "title": "Me & My Dog"},
    ],

    "Sea of Feels": [
        {"artist": "Bon Iver", "title": "Holocene"},
        {"artist": "The National", "title": "Bloodbuzz Ohio"},
        {"artist": "Sufjan Stevens", "title": "Death With Dignity"},
        {"artist": "Sigur Rós", "title": "Ára bátur"},
        {"artist": "Explosions in the Sky", "title": "Your Hand in Mine"},
        {"artist": "Daughter", "title": "Youth"},
        {"artist": "Portishead", "title": "Glory Box"},
        {"artist": "James Blake", "title": "Retrograde"},
        {"artist": "Weyes Blood", "title": "Movies"},
        {"artist": "Sharon Van Etten", "title": "Serpents"},
    ],

    "Dance Alone": [
        {"artist": "Robyn", "title": "Dancing On My Own"},
        {"artist": "Carly Rae Jepsen", "title": "Run Away with Me"},
        {"artist": "Dua Lipa", "title": "Levitating"},
        {"artist": "Lizzo", "title": "Juice"},
        {"artist": "Janelle Monáe", "title": "Make Me Feel"},
        {"artist": "Kylie Minogue", "title": "Can't Get You Out of My Head"},
        {"artist": "Madonna", "title": "Like a Prayer"},
        {"artist": "Charli XCX", "title": "BOOM CLAP"},
        {"artist": "ABBA", "title": "Dancing Queen"},
        {"artist": "Troye Sivan", "title": "My My My!"},
    ],

    "Rage Quit": [
        {"artist": "System of a Down", "title": "Chop Suey!"},
        {"artist": "Slipknot", "title": "Duality"},
        {"artist": "Korn", "title": "Freak on a Leash"},
        {"artist": "Limp Bizkit", "title": "Break Stuff"},
        {"artist": "Rage Against the Machine", "title": "Killing in the Name"},
        {"artist": "Deftones", "title": "My Own Summer (Shove It)"},
        {"artist": "Nine Inch Nails", "title": "Head Like a Hole"},
        {"artist": "Bring Me the Horizon", "title": "Antivist"},
        {"artist": "Hatebreed", "title": "Perseverance"},
        {"artist": "Converge", "title": "Concubine"},
    ],

    "Tenderness": [
        {"artist": "Sufjan Stevens", "title": "Mystery of Love"},
        {"artist": "Novo Amor", "title": "Anchor"},
        {"artist": "Gregory Alan Isakov", "title": "The Stable Song"},
        {"artist": "Hozier", "title": "Cherry Wine"},
        {"artist": "Iron & Wine", "title": "Naked As We Came"},
        {"artist": "Father John Misty", "title": "Strange Encounter"},
        {"artist": "Angel Olsen", "title": "Intern"},
        {"artist": "Mitski", "title": "Me and My Husband"},
        {"artist": "Big Thief", "title": "Not"},
        {"artist": "Adrianne Lenker", "title": "ingydar"},
    ],
}

# ---------------------------------------------------------------------------
# Remove duplicates that crept into the initial EXTENSIONS dict (the
# "Anime Openings" entry had artist/title swapped for Yui – strip the bad one)
# ---------------------------------------------------------------------------

def dedupe(entries):
    """Remove exact duplicate dicts from a list (preserving order)."""
    seen = set()
    out = []
    for e in entries:
        key = (e["artist"].lower(), e["title"].lower())
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def main():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    total_added = 0
    report_lines = []

    # ── Task 1: extend existing moods ───────────────────────────────────────
    for mood, new_tracks in EXTENSIONS.items():
        if mood not in data:
            print(f"[WARN] Mood not found in file: {mood!r}")
            continue

        # Build a set of existing (artist, title) pairs (case-insensitive)
        existing_keys = {
            (e["artist"].lower(), e["title"].lower())
            for e in data[mood]
        }

        to_add = []
        for track in new_tracks:
            key = (track["artist"].lower(), track["title"].lower())
            if key not in existing_keys:
                to_add.append(track)
                existing_keys.add(key)

        data[mood].extend(to_add)
        count = len(to_add)
        total_added += count
        report_lines.append(
            f"  [EXTEND] {mood!r:45s} +{count:2d}  -> {len(data[mood])} total"
        )

    # ── Task 2: add new moods ────────────────────────────────────────────────
    for mood, tracks in NEW_MOODS.items():
        if mood in data:
            print(f"[WARN] Mood already exists, skipping: {mood!r}")
            continue
        data[mood] = dedupe(tracks)
        count = len(data[mood])
        total_added += count
        report_lines.append(
            f"  [NEW]    {mood!r:45s} +{count:2d}  -> {count} total"
        )

    # ── Write back ───────────────────────────────────────────────────────────
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("\nAnchor patch complete!")
    print(f"Total anchors added: {total_added}")
    print(f"Total moods in file: {len(data)}\n")
    for line in report_lines:
        print(line)


if __name__ == "__main__":
    main()
