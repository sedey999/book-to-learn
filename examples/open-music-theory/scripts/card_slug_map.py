# 精确的 card_id -> pressbooks slug 硬编码映射表
# 每张卡片精确对应一个章节页面，按 OMT2 书籍目录对照并逐一验证
# URL = https://viva.pressbooks.pub/openmusictheory/chapter/<slug>/
# 验证日期：2026-07-20

CARD_SLUG_MAP = {
    # ==== Chapter 1: Fundamentals ====
    "ch01-01": "introduction-to-western-musical-notation",
    "ch01-02": "notation-of-notes-clefs-and-ledger-lines",
    "ch01-03": "clefs",                              # Reading Clefs
    "ch01-04": "the-keyboard-and-grand-staff",
    "ch01-05": "half-and-whole-steps",
    "ch01-06": "aspn",                               # American Standard Pitch Notation
    "ch01-07": "other-aspects-of-notation",
    "ch01-08": "notating-rhythm",                    # Rhythmic and Rest Values (renamed in OMT2)
    "ch01-09": "simple-meter-and-time-signatures",
    "ch01-10": "compound-meters-and-time-signatures",
    "ch01-11": "other-rhythmic-essentials",
    "ch01-12": "major-scales",
    "ch01-13": "minor-scales",
    "ch01-14": "intro-to-diatonic-modes-and-the-chromatic-scale",
    "ch01-15": "the-basics-of-sight-singing-and-dictation",
    "ch01-16": "intervals",
    "ch01-17": "triads",
    "ch01-18": "seventh-chords",
    "ch01-19": "inversion",                          # Inversion and Figured Bass (inversion page covers it)
    "ch01-20": "roman-numerals",                     # Roman Numerals and SATB Chord Construction
    "ch01-21": "texture",
    "ch01-22": "hypermeter2",                        # "Hypermeter (new version)" has examples; hypermeter has 0 figures
    "ch01-23": "metrical-dissonance",
    "ch01-24": "twentieth-century-rhythmic-techniques",
    "ch01-25": "examples-for-sight-counting-and-sight-singing",
    "ch01-26": "examples-for-sight-counting-and-sight-singing-level-2",

    # ==== Chapter 2: Species Counterpoint ====
    "ch02-01": "species-counterpoint",               # Introduction to Species Counterpoint
    "ch02-02": "first-species-counterpoint",
    "ch02-03": "second-species-counterpoint",
    "ch02-04": "third-species-counterpoint",
    "ch02-05": "fourth-species-counterpoint",
    "ch02-06": "fifth-species-counterpoint",
    "ch02-07": "gradus-ad-parnassum-exercises",
    "ch02-08": "16th-century-contrapuntal-style",
    "ch02-09": "high-baroque-fugal-exposition",
    "ch02-10": "ground-bass",
    "ch02-11": "galant-schemas",
    "ch02-12": "galant-schemas-summary",
    "ch02-13": "rule-of-the-octave",

    # ==== Chapter 3: Form ====
    "ch03-01": "foundational-concepts",
    "ch03-02": "phrase-archetypes-unique-forms",
    "ch03-03": "hybrid-phrase-level-forms",
    "ch03-04": "expansion-and-contraction",
    "ch03-05": "formal-sections-in-general",
    "ch03-06": "binary-form",
    "ch03-07": "ternary-form",                       # Ternary Form
    "ch03-08": "sonata-form",
    "ch03-09": "rondo",

    # ==== Chapter 4: Harmony ====
    "ch04-01": "intro-to-harmony",
    "ch04-02": "strengthening-endings-with-v7",
    "ch04-03": "strong-predominants",                # Strengthening Endings with Strong Predominants
    "ch04-04": "embellishing-tones",
    "ch04-05": "cadential-64",
    "ch04-06": "inverted-v7s",
    "ch04-07": "performing-harmonic-analysis-using-the-phrase-model",
    "ch04-08": "leading-tone-chord",
    "ch04-09": "64-chords-as-prolongations",
    "ch04-10": "plagal-motion",
    "ch04-11": "la-in-the-bass",
    "ch04-12": "the-mediant",
    "ch04-13": "predominant-seventh-chords",
    "ch04-14": "tonicization",
    "ch04-15": "extended-tonicization-and-modulation-to-closely-related-keys",

    # ==== Chapter 5: Chromatic Harmony ====
    "ch05-01": "modal-mixture",
    "ch05-02": "bii6",                               # Neapolitan Sixth Chords
    "ch05-03": "augmented-sixth-chords",
    "ch05-04": "common-tone-chords",
    "ch05-05": "harmonic-elision",
    "ch05-06": "reinterpreting-augmented-sixth-chords",  # Chromatic Modulation (page title is this, covers distant modulation)
    "ch05-07": "reinterpreting-augmented-sixth-chords",  # Reinterpreting Diminished 7ths (same page section)
    "ch05-08": "augmented-options",
    "ch05-09": "equal-divisions-of-the-octave",
    "ch05-10": "chromatic-sequences",
    "ch05-11": "diatonic-sequences",                 # Parallel Chromatic Sequences (Diatonic Sequences in Middles)
    "ch05-12": "the-omnibus-progression",
    "ch05-13": "altered-and-extended-dominant-chords",
    "ch05-14": "neo-riemannian-triadic-progressions",
    "ch05-15": "mediants",

    # ==== Chapter 6: Jazz ====
    "ch06-01": "swing-rhythms",
    "ch06-02": "chord-symbols",
    "ch06-03": "jazz-voicings",
    "ch06-04": "ii-v-i",
    "ch06-05": "jazz-embellishing-chords",           # Embellishing Chords
    "ch06-06": "substitutions",
    "ch06-07": "chord-scale-theory",
    "ch06-08": "blues-harmony",
    "ch06-09": "blues-melodies-and-the-blues-scale",

    # ==== Chapter 7: Pop & Rock ====
    "ch07-01": "rhythm-and-meter-in-pop-music",
    "ch07-02": "melody-and-phrasing",
    "ch07-03": "intro-to-form-in-popular-music",
    "ch07-04": "aaba-and-strophic-form",
    "ch07-05": "verse-chorus-form",
    "ch07-06": "intro-to-pop-schemas",               # Introduction to Harmonic Schemas in Pop Music
    "ch07-07": "blues-based-schemas",
    "ch07-08": "4-chord-schemas",
    "ch07-09": "classical-schemas",
    "ch07-10": "puff-schemas",
    "ch07-11": "modal-schemas",
    "ch07-12": "pentatonic-harmony",
    "ch07-13": "fragile-absent-and-emergent-tonics",
    "ch07-14": "drumbeats",

    # ==== Chapter 8: Post-Tonal Theory ====
    "ch08-01": "pitch-and-pitch-class",
    "ch08-02": "intervals-in-integer-notation",
    "ch08-03": "pc-sets-normal-order-and-transformations",
    "ch08-04": "set-class-and-prime-form",
    "ch08-05": "analyzing-with-set-theory",
    "ch08-06": "diatonic-modes",
    "ch08-07": "collections",
    "ch08-08": "analyzing-with-collections-scales-and-modes",

    # ==== Chapter 9: Twelve-Tone ====
    "ch09-01": "basics-of-twelve-tone-theory",
    "ch09-02": "naming-conventions-for-rows",
    "ch09-03": "row-properties",
    "ch09-04": "twelve-tone-analysis-examples-webern-op-21-and-24",
    "ch09-05": "composing-with-twelve-tones",
    "ch09-06": "history-and-context-of-serialism",

    # ==== Chapter 10: Orchestration ====
    "ch10-01": "core-principles-of-orchestration",
    "ch10-02": "subtle-color-changes",               # "Subtle Color Changes" (US spelling in URL)
    "ch10-03": "transcription-from-piano",
}
