"""
scripts/expand_anchors.py
Expand all mood anchor sets to 10+ tracks.
Run: python scripts/expand_anchors.py
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(ROOT, "data", "mood_anchors.json"), encoding="utf-8") as f:
    anchors = json.load(f)

# New anchors to add per mood. Only tracks that unambiguously belong.
# Format: [{"artist": "...", "title": "..."}]
NEW_ANCHORS = {
    "Acoustic Corner": [
        {"artist": "José González", "title": "Heartbeats"},
        {"artist": "Ben Howard", "title": "Keep Your Head Up"},
        {"artist": "Laura Marling", "title": "Rambling Man"},
        {"artist": "Sufjan Stevens", "title": "Death With Dignity"},
    ],
    "Adrenaline": [
        {"artist": "Metallica", "title": "Master of Puppets"},
        {"artist": "Slipknot", "title": "Before I Forget"},
        {"artist": "System of a Down", "title": "BYOB"},
        {"artist": "Bring Me the Horizon", "title": "Throne"},
    ],
    "Afro-Fusion Golden Hour": [
        {"artist": "Rema", "title": "Calm Down"},
        {"artist": "Omah Lay", "title": "Understand"},
        {"artist": "Joeboy", "title": "Beginning"},
        {"artist": "Ayra Starr", "title": "Rush"},
    ],
    "Afterparty": [
        {"artist": "Swedish House Mafia", "title": "Don't You Worry Child"},
        {"artist": "Martin Garrix", "title": "Animals"},
        {"artist": "Zedd", "title": "Clarity"},
        {"artist": "Tiësto", "title": "The Business"},
    ],
    "Amapiano Sunset": [
        {"artist": "Kabza De Small", "title": "Sponono"},
        {"artist": "DJ Maphorisa", "title": "Izolo"},
        {"artist": "Focalistic", "title": "Ke Star"},
        {"artist": "Samthing Soweto", "title": "Akulaleki"},
    ],
    "Anti-Hero Receipts": [
        {"artist": "Drake", "title": "Headlines"},
        {"artist": "Nicki Minaj", "title": "Super Bass"},
        {"artist": "Lil Wayne", "title": "A Milli"},
        {"artist": "Meek Mill", "title": "Dreams and Nightmares"},
    ],
    "Baroque Pop Melodrama": [
        {"artist": "Sufjan Stevens", "title": "Chicago"},
        {"artist": "Joanna Newsom", "title": "Sadie"},
        {"artist": "Regina Spektor", "title": "Samson"},
        {"artist": "Andrew Bird", "title": "Fake Palindromes"},
    ],
    "Brass & Drumline Energy": [
        {"artist": "Rebirth Brass Band", "title": "Do Watcha Wanna"},
        {"artist": "Youngblood Brass Band", "title": "Assault"},
        {"artist": "Hypnotic Brass Ensemble", "title": "War"},
        {"artist": "Hot 8 Brass Band", "title": "Sexual Healing"},
    ],
    "Country Roads": [
        {"artist": "John Denver", "title": "Take Me Home, Country Roads"},
        {"artist": "Dolly Parton", "title": "Jolene"},
        {"artist": "Kenny Rogers", "title": "The Gambler"},
        {"artist": "Garth Brooks", "title": "Friends in Low Places"},
    ],
    "Country Story Hour": [
        {"artist": "Jason Isbell", "title": "Cover Me Up"},
        {"artist": "Sturgill Simpson", "title": "Turtles All the Way Down"},
        {"artist": "Tyler Childers", "title": "Feathered Indians"},
        {"artist": "Colter Wall", "title": "Sleeping on the Blacktop"},
    ],
    "Disco Lights": [
        {"artist": "Gloria Gaynor", "title": "I Will Survive"},
        {"artist": "Chic", "title": "Good Times"},
        {"artist": "Sister Sledge", "title": "We Are Family"},
        {"artist": "KC and the Sunshine Band", "title": "That's the Way (I Like It)"},
    ],
    "Drill Confessions": [
        {"artist": "Central Cee", "title": "Doja"},
        {"artist": "Fivio Foreign", "title": "Big Drip"},
        {"artist": "Lil Durk", "title": "The Voice"},
        {"artist": "Polo G", "title": "Pop Out"},
    ],
    "Flex Tape": [
        {"artist": "Gunna", "title": "Drip Too Hard"},
        {"artist": "Young Thug", "title": "Best Friend"},
        {"artist": "Lil Baby", "title": "Drip Too Hard"},
        {"artist": "Future", "title": "Mask Off"},
    ],
    "Golden Hour": [
        {"artist": "Harry Styles", "title": "Watermelon Sugar"},
        {"artist": "Lizzo", "title": "Good as Hell"},
        {"artist": "Dua Lipa", "title": "Levitating"},
        {"artist": "Bruno Mars", "title": "Uptown Funk"},
    ],
    "Gospel Fire": [
        {"artist": "Kirk Franklin", "title": "Stomp"},
        {"artist": "Yolanda Adams", "title": "Open My Heart"},
        {"artist": "Fred Hammond", "title": "You Are My Daily Bread"},
        {"artist": "Mary Mary", "title": "Shackles (Praise You)"},
    ],
    "Healing Kind": [
        {"artist": "Nick Drake", "title": "Pink Moon"},
        {"artist": "Fleet Foxes", "title": "White Winter Hymnal"},
        {"artist": "Sufjan Stevens", "title": "Death With Dignity"},
        {"artist": "Grouper", "title": "Vapor Trail"},
    ],
    "Heartbreak": [
        {"artist": "Sam Smith", "title": "Stay with Me"},
        {"artist": "Lana Del Rey", "title": "Video Games"},
        {"artist": "Olivia Rodrigo", "title": "drivers license"},
        {"artist": "Billie Eilish", "title": "when the party's over"},
    ],
    "Hollow": [
        {"artist": "The National", "title": "Bloodbuzz Ohio"},
        {"artist": "Elliott Smith", "title": "Between the Bars"},
        {"artist": "Sufjan Stevens", "title": "Death With Dignity"},
        {"artist": "Cigarettes After Sex", "title": "Apocalypse"},
    ],
    "Hyperpop": [
        {"artist": "100 gecs", "title": "Hand Crushed by a Mallet"},
        {"artist": "Dorian Electra", "title": "Flamboyant"},
        {"artist": "Hannah Diamond", "title": "Make Believe"},
        {"artist": "Charli XCX", "title": "Vroom Vroom"},
    ],
    "Indie Bedroom": [
        {"artist": "beabadoobee", "title": "Coffee"},
        {"artist": "Men I Trust", "title": "Show Me How"},
        {"artist": "Still Woozy", "title": "Goodie Bag"},
        {"artist": "Clairo", "title": "Pretty Girl"},
    ],
    "Industrial Gothic Floor": [
        {"artist": "Nine Inch Nails", "title": "Head Like a Hole"},
        {"artist": "Ministry", "title": "Jesus Built My Hotrod"},
        {"artist": "KMFDM", "title": "Juke Joint Jezebel"},
        {"artist": "Front Line Assembly", "title": "Mindphaser"},
    ],
    "J-Metal": [
        {"artist": "Babymetal", "title": "Gimme Chocolate!!"},
        {"artist": "Maximum the Hormone", "title": "Zetsubou Billy"},
        {"artist": "Dir En Grey", "title": "Obscure"},
        {"artist": "Crossfaith", "title": "Omen"},
    ],
    "J-Pop": [
        {"artist": "Kenshi Yonezu", "title": "Lemon"},
        {"artist": "LiSA", "title": "Gurenge"},
        {"artist": "Aimyon", "title": "Marry Me?"},
        {"artist": "Official HIGE DANdism", "title": "Subtitle"},
    ],
    "Kawaii Metal Sparkle": [
        {"artist": "Babymetal", "title": "Karate"},
        {"artist": "Ladybaby", "title": "Nippon Manju"},
        {"artist": "PassCode", "title": "CLARITY"},
        {"artist": "Himekami", "title": "Yuki no Hana"},
    ],
    "Late Night Drive": [
        {"artist": "Kavinsky", "title": "Nightcall"},
        {"artist": "Chromatics", "title": "Night Drive"},
        {"artist": "M83", "title": "Midnight City"},
        {"artist": "Com Truise", "title": "Galactic Melt"},
    ],
    "Latin Ballroom Heat": [
        {"artist": "Marc Anthony", "title": "Vivir Mi Vida"},
        {"artist": "Celia Cruz", "title": "La Vida Es Un Carnaval"},
        {"artist": "Jennifer Lopez", "title": "On the Floor"},
        {"artist": "Shakira", "title": "Whenever, Wherever"},
    ],
    "Latin Heat": [
        {"artist": "Bad Bunny", "title": "Tití Me Preguntó"},
        {"artist": "J Balvin", "title": "Mi Gente"},
        {"artist": "Ozuna", "title": "Taki Taki"},
        {"artist": "Maluma", "title": "Felices los 4"},
    ],
    "Liminal": [
        {"artist": "Stars of the Lid", "title": "Requiem for Dying Mothers Pt. 2"},
        {"artist": "William Basinski", "title": "Disintegration Loop 1.1"},
        {"artist": "Tim Hecker", "title": "Hatred of Music I"},
        {"artist": "Grouper", "title": "Invisible"},
    ],
    "Meditation Bath": [
        {"artist": "Nils Frahm", "title": "All Melody"},
        {"artist": "Moby", "title": "Porcelain"},
        {"artist": "Hammock", "title": "Breathturn"},
        {"artist": "Steve Reich", "title": "Music for 18 Musicians"},
    ],
    "Metal Testimony": [
        {"artist": "Stryper", "title": "To Hell with the Devil"},
        {"artist": "Skillet", "title": "Monster"},
        {"artist": "Petra", "title": "This Means War"},
        {"artist": "Flyleaf", "title": "All Around Me"},
    ],
    "Minimal Techno Tunnel": [
        {"artist": "Richie Hawtin", "title": "Spastik"},
        {"artist": "Robert Hood", "title": "Moveable Parts"},
        {"artist": "Plastikman", "title": "Spastik"},
        {"artist": "Jeff Mills", "title": "The Bells"},
    ],
    "Money Talks": [
        {"artist": "Rick Ross", "title": "Hustlin'"},
        {"artist": "Jay-Z", "title": "Dead Presidents II"},
        {"artist": "Cardi B", "title": "Bodak Yellow"},
        {"artist": "Migos", "title": "Bad and Boujee"},
    ],
    "Morning Ritual": [
        {"artist": "Norah Jones", "title": "Don't Know Why"},
        {"artist": "Frank Sinatra", "title": "Fly Me to the Moon"},
        {"artist": "Vulfpeck", "title": "Dean Town"},
        {"artist": "Rex Orange County", "title": "Best Friend"},
    ],
    "Neo-Soul": [
        {"artist": "Erykah Badu", "title": "On & On"},
        {"artist": "D'Angelo", "title": "Untitled (How Does It Feel)"},
        {"artist": "Maxwell", "title": "Fortunate"},
        {"artist": "Jill Scott", "title": "Golden"},
    ],
    "Open Road": [
        {"artist": "Bruce Springsteen", "title": "Born to Run"},
        {"artist": "Tom Petty", "title": "Running Down a Dream"},
        {"artist": "Eagles", "title": "Life in the Fast Lane"},
        {"artist": "Creedence Clearwater Revival", "title": "Born on the Bayou"},
    ],
    "Overflow": [
        {"artist": "James Blake", "title": "Limit to Your Love"},
        {"artist": "FKA Twigs", "title": "Two Weeks"},
        {"artist": "Sevdaliza", "title": "Marilyn Monroe"},
        {"artist": "Kelela", "title": "LMK"},
    ],
    "Overthinking": [
        {"artist": "The 1975", "title": "Robbers"},
        {"artist": "boygenius", "title": "Motion Sickness"},
        {"artist": "Mitski", "title": "Nobody"},
        {"artist": "MUNA", "title": "Silk Chiffon"},
    ],
    "Pluggnb Heartache": [
        {"artist": "Bryson Tiller", "title": "Exchange"},
        {"artist": "6lack", "title": "PRBLMS"},
        {"artist": "Brent Faiyaz", "title": "Gravity"},
        {"artist": "Summer Walker", "title": "Girls Need Love"},
    ],
    "Queer Dance Confetti": [
        {"artist": "Kim Petras", "title": "Heart to Break"},
        {"artist": "Troye Sivan", "title": "My My My!"},
        {"artist": "Years & Years", "title": "King"},
        {"artist": "Todrick Hall", "title": "Nails, Hair, Hips, Heels"},
    ],
    "Rage Lift": [
        {"artist": "Deftones", "title": "My Own Summer (Shove It)"},
        {"artist": "Tool", "title": "Schism"},
        {"artist": "Pantera", "title": "Walk"},
        {"artist": "Disturbed", "title": "Down with the Sickness"},
    ],
    "Rainy Window": [
        {"artist": "Mazzy Star", "title": "Fade Into You"},
        {"artist": "Portishead", "title": "Glory Box"},
        {"artist": "Nick Cave & The Bad Seeds", "title": "Into My Arms"},
        {"artist": "Lana Del Rey", "title": "Summertime Sadness"},
    ],
    "Raw Emotion": [
        {"artist": "Alanis Morissette", "title": "You Oughta Know"},
        {"artist": "Fiona Apple", "title": "Criminal"},
        {"artist": "Sinéad O'Connor", "title": "Nothing Compares 2 U"},
        {"artist": "Tracy Chapman", "title": "Fast Car"},
    ],
    "Runaway Highways": [
        {"artist": "Tom Petty", "title": "Free Fallin'"},
        {"artist": "Sheryl Crow", "title": "Every Day Is a Winding Road"},
        {"artist": "Fleetwood Mac", "title": "Go Your Own Way"},
        {"artist": "Bob Seger", "title": "Night Moves"},
    ],
    "Same Vibe Different Genre": [
        {"artist": "Radiohead", "title": "No Surprises"},
        {"artist": "Nick Cave & The Bad Seeds", "title": "Red Right Hand"},
        {"artist": "Sufjan Stevens", "title": "Mystery of Love"},
        {"artist": "Weyes Blood", "title": "Andromeda"},
    ],
    "Sea Shanty Singalong": [
        {"artist": "The Longest Johns", "title": "Wellerman"},
        {"artist": "Nathan Evans", "title": "Wellerman (Sea Shanty)"},
        {"artist": "Irish Rovers", "title": "Drunken Sailor"},
        {"artist": "Whiskey Pirates", "title": "Leave Her Johnny"},
    ],
    "Slow Jams": [
        {"artist": "Keith Sweat", "title": "Nobody"},
        {"artist": "Boyz II Men", "title": "I'll Make Love to You"},
        {"artist": "R. Kelly", "title": "Bump N' Grind"},
        {"artist": "Jodeci", "title": "Cry for You"},
    ],
    "Smoke & Mirrors": [
        {"artist": "Queens of the Stone Age", "title": "No One Knows"},
        {"artist": "Arctic Monkeys", "title": "Do I Wanna Know?"},
        {"artist": "Beck", "title": "Loser"},
        {"artist": "Gorillaz", "title": "Feel Good Inc."},
    ],
    "Songs About Goodbye": [
        {"artist": "Green Day", "title": "Good Riddance (Time of Your Life)"},
        {"artist": "Semisonic", "title": "Closing Time"},
        {"artist": "Sarah McLachlan", "title": "I Will Remember You"},
        {"artist": "Boyz II Men", "title": "It's So Hard to Say Goodbye to Yesterday"},
    ],
    "Sunday Reset": [
        {"artist": "Norah Jones", "title": "Come Away with Me"},
        {"artist": "John Mayer", "title": "Slow Dancing in a Burning Room"},
        {"artist": "Jack Johnson", "title": "Better Together"},
        {"artist": "Vance Joy", "title": "Riptide"},
    ],
    "Sundown": [
        {"artist": "Fleetwood Mac", "title": "The Chain"},
        {"artist": "Eagles", "title": "Peaceful Easy Feeling"},
        {"artist": "James Taylor", "title": "Fire and Rain"},
        {"artist": "Crosby, Stills, Nash & Young", "title": "Teach Your Children"},
    ],
    "Symphonic Metal Epics": [
        {"artist": "Nightwish", "title": "Ghost Love Score"},
        {"artist": "Epica", "title": "Cry for the Moon"},
        {"artist": "Therion", "title": "To Mega Therion"},
        {"artist": "Evanescence", "title": "My Immortal"},
    ],
    "Villain Arc": [
        {"artist": "Pusha T", "title": "Infrared"},
        {"artist": "Rick Ross", "title": "B.M.F. (Blowin' Money Fast)"},
        {"artist": "Migos", "title": "Bad and Boujee"},
        {"artist": "Future", "title": "Mask Off"},
    ],
    "Warehouse Techno": [
        {"artist": "Charlotte de Witte", "title": "Doppler"},
        {"artist": "Alignment", "title": "Renegade"},
        {"artist": "Amelie Lens", "title": "Exhale"},
        {"artist": "I Hate Models", "title": "Rave Is Now"},
    ],
    "3 AM Unsent Texts": [
        {"artist": "Phoebe Bridgers", "title": "Moon Song"},
        {"artist": "Hozier", "title": "From Eden"},
        {"artist": "Lorde", "title": "Liability"},
    ],
    "Anime Endings": [
        {"artist": "Yui", "title": "Again"},
        {"artist": "Cö shu Nie", "title": "Asphyxia"},
        {"artist": "Sawano Hiroyuki", "title": "APOCRYPHA"},
    ],
    "Anime OST Energy": [
        {"artist": "Hiroyuki Sawano", "title": "Vogel im Käfig"},
        {"artist": "Yoko Shimomura", "title": "Dearly Beloved"},
        {"artist": "Nobuo Uematsu", "title": "One-Winged Angel"},
    ],
    "Anime Openings": [
        {"artist": "Linked Horizon", "title": "Guren no Yumiya"},
        {"artist": "Asian Kung-Fu Generation", "title": "Haruka Kanata"},
        {"artist": "Flow", "title": "GO!!!"},
    ],
    "Bedroom Pop Diary": [
        {"artist": "Clairo", "title": "Flaming Hot Cheetos"},
        {"artist": "Wallows", "title": "Are You Bored Yet?"},
        {"artist": "TV Girl", "title": "Birds Don't Sing"},
    ],
    "Chillhop Cafe": [
        {"artist": "Idealism", "title": "daydream"},
        {"artist": "Philanthrope", "title": "Settling"},
        {"artist": "C418", "title": "Sweden"},
    ],
    "Classical Calm": [
        {"artist": "Frédéric Chopin", "title": "Nocturne No. 2 in E-flat Major"},
        {"artist": "Erik Satie", "title": "Gymnopédie No. 1"},
        {"artist": "Johann Sebastian Bach", "title": "Cello Suite No. 1 in G Major"},
    ],
    "Cloud Rap Haze": [
        {"artist": "Bones", "title": "WhereTheTreesMeetTheFreeway"},
        {"artist": "Corbin", "title": "Revenge"},
        {"artist": "Lil Peep", "title": "Awful Things"},
    ],
    "Deep Focus": [
        {"artist": "Brian Eno", "title": "1/1"},
        {"artist": "Max Richter", "title": "On the Nature of Daylight"},
        {"artist": "Tycho", "title": "Awake"},
    ],
    "Dream Pop Haze": [
        {"artist": "Cocteau Twins", "title": "Heaven or Las Vegas"},
        {"artist": "Beach House", "title": "Space Song"},
        {"artist": "Wild Nothing", "title": "Chinatown"},
    ],
    "Drill": [
        {"artist": "Pop Smoke", "title": "Dior"},
        {"artist": "Headie One", "title": "Know Better"},
        {"artist": "Unknown T", "title": "Homerton B"},
    ],
    "Emo Hour": [
        {"artist": "My Chemical Romance", "title": "I'm Not Okay (I Promise)"},
        {"artist": "Paramore", "title": "Decode"},
        {"artist": "Fall Out Boy", "title": "Sugar, We're Goin Down"},
    ],
    "Euphoric Rave": [
        {"artist": "Skrillex", "title": "Scary Monsters and Nice Sprites"},
        {"artist": "Knife Party", "title": "Internet Friends"},
        {"artist": "Deadmau5", "title": "Ghosts 'n' Stuff"},
    ],
    "Goth / Darkwave": [
        {"artist": "Siouxsie and the Banshees", "title": "Cities in Dust"},
        {"artist": "Bauhaus", "title": "Bela Lugosi's Dead"},
        {"artist": "Sisters of Mercy", "title": "This Corrosion"},
    ],
    "Hard Reset": [
        {"artist": "Röyksopp", "title": "Remind Me"},
        {"artist": "Bonobo", "title": "Kong"},
        {"artist": "Floating Points", "title": "LesAlpx"},
    ],
    "Hyperpop Emotional Crash": [
        {"artist": "SOPHIE", "title": "It's Okay to Cry"},
        {"artist": "Arca", "title": "Riquiquí"},
        {"artist": "Eartheater", "title": "Peripheral"},
    ],
    "Jazz Nights": [
        {"artist": "Miles Davis", "title": "So What"},
        {"artist": "John Coltrane", "title": "A Love Supreme, Pt. I"},
        {"artist": "Thelonious Monk", "title": "Round Midnight"},
    ],
    "K-Pop Zone": [
        {"artist": "aespa", "title": "Next Level"},
        {"artist": "Stray Kids", "title": "God's Menu"},
        {"artist": "ITZY", "title": "DALLA DALLA"},
    ],
    "Lo-Fi Flow": [
        {"artist": "j^p^n", "title": "Snowfall"},
        {"artist": "Jinsang", "title": "Solitude"},
        {"artist": "Kupla", "title": "Flowers"},
    ],
    "Metal Storm": [
        {"artist": "Gojira", "title": "Stranded"},
        {"artist": "Mastodon", "title": "Blood and Thunder"},
        {"artist": "Lamb of God", "title": "Redneck"},
    ],
    "Midnight Clarity": [
        {"artist": "Frank Ocean", "title": "White Ferrari"},
        {"artist": "Mac Miller", "title": "Small Worlds"},
        {"artist": "SZA", "title": "20 Something"},
    ],
    "Nostalgia": [
        {"artist": "Semisonic", "title": "Closing Time"},
        {"artist": "Savage Garden", "title": "Truly Madly Deeply"},
        {"artist": "Eagle-Eye Cherry", "title": "Save Tonight"},
    ],
    "Old School Hip-Hop": [
        {"artist": "A Tribe Called Quest", "title": "Electric Relaxation"},
        {"artist": "De La Soul", "title": "Me Myself and I"},
        {"artist": "Public Enemy", "title": "Fight the Power"},
    ],
    "Phonk Season": [
        {"artist": "Kordhell", "title": "Murder in My Mind"},
        {"artist": "Ghostemane", "title": "Mercury: Retrograde"},
        {"artist": "Night Lovell", "title": "Dark Light"},
    ],
    "Psychedelic": [
        {"artist": "Pink Floyd", "title": "Comfortably Numb"},
        {"artist": "The Doors", "title": "Break On Through"},
        {"artist": "Jefferson Airplane", "title": "Somebody to Love"},
    ],
    "Punk Sprint": [
        {"artist": "The Clash", "title": "London Calling"},
        {"artist": "Bad Brains", "title": "Pay to Cum"},
        {"artist": "Black Flag", "title": "Rise Above"},
    ],
    "Shoegaze Breakups": [
        {"artist": "My Bloody Valentine", "title": "Sometimes"},
        {"artist": "Slowdive", "title": "Alison"},
        {"artist": "Ride", "title": "Vapour Trail"},
    ],
    "Soft Hours": [
        {"artist": "Frank Ocean", "title": "Ivy"},
        {"artist": "Daniel Caesar", "title": "Get You"},
        {"artist": "Sade", "title": "No Ordinary Love"},
    ],
    "Songs About Home": [
        {"artist": "Mumford & Sons", "title": "After the Storm"},
        {"artist": "The Lumineers", "title": "Ho Hey"},
        {"artist": "Fleet Foxes", "title": "Helplessness Blues"},
    ],
    "Synthwave Nights": [
        {"artist": "Kavinsky", "title": "Nightcall"},
        {"artist": "Gunship", "title": "Tech Noir"},
        {"artist": "FM-84", "title": "Running in the Night"},
    ],
    "Tropicana": [
        {"artist": "Daddy Yankee", "title": "Gasolina"},
        {"artist": "Pitbull", "title": "Give Me Everything"},
        {"artist": "Shakira", "title": "Hips Don't Lie"},
    ],
    "Vaporwave": [
        {"artist": "Macintosh Plus", "title": "リサフランク420 / 現代のコンピュー"},
        {"artist": "Saint Pepsi", "title": "Private Caller"},
        {"artist": "Blank Banshee", "title": "Teen Pregnancy"},
    ],
    "Weightless": [
        {"artist": "Max Richter", "title": "On the Nature of Daylight"},
        {"artist": "Nils Frahm", "title": "Says"},
        {"artist": "Johann Johannsson", "title": "The Sun's Gone Dim"},
    ],
    "Dark Pop": [
        {"artist": "Halsey", "title": "Without Me"},
        {"artist": "Melanie Martinez", "title": "Tag, You're It"},
    ],
}

added_total = 0
for mood, new_tracks in NEW_ANCHORS.items():
    if mood not in anchors:
        print(f"SKIP (not in anchors): {mood}")
        continue
    existing = anchors[mood]
    existing_keys = {(a["artist"].lower(), a["title"].lower()) for a in existing}
    actually_added = []
    for t in new_tracks:
        key = (t["artist"].lower(), t["title"].lower())
        if key not in existing_keys:
            existing.append(t)
            existing_keys.add(key)
            actually_added.append(t["artist"] + " - " + t["title"])
    if actually_added:
        added_total += len(actually_added)
    anchors[mood] = existing

with open(os.path.join(ROOT, "data", "mood_anchors.json"), "w", encoding="utf-8") as f:
    json.dump(anchors, f, ensure_ascii=False, indent=2)

total = sum(len(a) for a in anchors.values())
avg = total / max(len(anchors), 1)
below10 = [(n, len(a)) for n, a in anchors.items() if len(a) < 10]
print(f"Added {added_total} anchors total")
print(f"Total: {total}  Avg: {avg:.1f}  Below-10: {len(below10)}")
print("Saved.")
