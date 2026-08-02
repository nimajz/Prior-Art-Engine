# ============================================================
# SECTION 1 — STOP-WORD SETS (ported 1:1 from original app.py)
# ============================================================

YAKE_STOPWORDS: frozenset = frozenset({
    "a","an","the","is","are","was","were","be","been","being",
    "have","has","had","do","does","did","will","would","could","should",
    "may","might","shall","can","need","i","you","he","she","it","we",
    "they","me","him","her","us","them","my","your","his","its","our",
    "their","this","that","these","those","and","but","or","nor","for",
    "yet","so","although","because","since","when","where","which","who",
    "whom","what","how","why","whether","about","above","across","after",
    "against","along","among","around","at","before","behind","below",
    "beside","between","by","down","during","except","from","in","inside",
    "into","near","of","off","on","onto","out","outside","over","past",
    "through","throughout","to","toward","under","until","up","upon",
    "with","within","without","very","just","also","too","even","still",
    "already","always","often","never","not","no","all","both","each",
    "few","more","most","other","some","such","than","then","here","there",
    "now","study","using","use","based","proposed","approach","method",
    "paper","work","show","shows","shown","results","result","data","new",
    "novel","present","presents","propose","demonstrates","investigate",
    "analysis","analyze","system","framework","model","task","problem",
    "solution","set","make","makes","made","feel","feels","create",
    "creates","see","sees","get","gets","give","gives","take","takes",
    "come","comes","look","looks","want","wants","need","needs","think",
    "thinks","know","knows","people","person","user","users","thing",
    "things","way","ways","case","cases","kind","type","types","lot",
    "lots","bit","sort","parts","time","times","day","year","years",
    "etc","like","many","much","used","via","different","various",
})

KW_STOPWORDS: frozenset = frozenset(YAKE_STOPWORDS | {
    "completely","novel","design","proposed","based","framework","algorithm",
    "automatically","intelligent","schedules","predict","household","patterns",
    "application","applications","learning","deep","machine","approach",
    "methods","systems","paper","works","studies","research","show","shows",
})
