"""Οι κατηγορίες με τις οποίες ξεκινά μια καινούργια βάση· μετά τις διαχειρίζεται ο χρήστης.

Αν η περιγραφή μιας κίνησης περιέχει κάποια λέξη-κλειδί (χωρίς διάκριση πεζών/κεφαλαίων),
η κίνηση μπαίνει στην κατηγορία. Οι κατηγορίες ελέγχονται με τη σειρά τους και τα κενά
μέσα στις λέξεις-κλειδιά μετράνε, π.χ. το «COM POI» πρέπει να προηγείται του «POI ».
"""

INCOME_OTHER = "Λοιπά έσοδα"
EXPENSE_OTHER = "Λοιπά έξοδα"
# Χρησιμοποιούνται όταν δεν ταιριάζει καμία λέξη-κλειδί, οπότε πρέπει να υπάρχουν πάντα.
SYSTEM_CATEGORIES = (INCOME_OTHER, EXPENSE_OTHER)

# (όνομα, κατηγορία εσόδων, λέξεις-κλειδιά)
DEFAULT_CATEGORIES = [
    ("Μισθός", True, ["ΜΙΣΘΟΔΟΣΙΑ"]),
    ("Προμήθειες τράπεζας", False, ["COM POI", "ΠΡΟΜΗΘΕΙΑ", "ΠΡΟΜΗΘ.", "ΕΞΟΔΑ ΤΗΡΗΣΗΣ"]),
    ("Εισερχόμενα εμβάσματα", True, ["POI ", "ΕΙΣΕΡΧΟΜΕΝΟ ΕΜΒΑΣΜΑ"]),
    ("Αναλήψεις ATM", False, ["ΑΝΑΛΗΨΗ ΜΕΤΡΗΤΩΝ", "ΑΤΜ NB", "ATM NB"]),
    ("Delivery φαγητού", False, ["eΦooΔ", "EFOOD", "WOLT", "BOX "]),
    ("Σούπερ μάρκετ", False, ["SKLAVENITIS", "ΣΚΛΑΒΕΝΙΤΗΣ", "AB VASSILOPOULOS", "LIDL", "MASOUTIS", "MY MARKET",
                              "GALAXIAS", "KRITIKOS", "MINI MARKET", "ARTODENTRON", "EVEREST"]),
    ("Καφές / Snacks", False, ["ENZYMO", "GIO GROUP", "CAFE", "CAFFE", "ESPRESSO", "BREW RATIO", "STARBU", "KIOSK",
                               "MATESI", "MY HOOD"]),
    ("Εστιατόρια", False, ["OUZERI", "GRILL", "GYRO", "ESTIASI", "ROOFGARDEN", "FOOD", "LADOKOLA"]),
    ("Τυχερά παιχνίδια", False, ["ALLWYN", "OPAP", "ΟΠΑΠ"]),
    ("Πληρωμές IRIS", False, ["IRIS"]),
    ("Υγεία", False, ["ΓΙΑΤΡ", "AFFIDEA", "DOCTOR", "ΦΑΡΜΑΚ", "PHARM", "IATR"]),
    ("Ενοίκιο", False, ["ENOIKIO", "ΕΝΟΙΚΙΟ"]),
    ("Λογαριασμοί", False, ["COSMOTE", "VODAFONE", "NOVA", "WIND", "MYF2G", "DEI ", "ΔΕΗ", "Δ.Ε.Η", "TELEKOM", "EYDAP",
                            "BEBAIVMENES OFEILES"]),
    ("Μετακινήσεις / Καύσιμα", False, ["UBER", "OASA", "KTEL", "AVIN", "EKO ", "STAIKOS", "SHELL", "BP ", "CARMATES",
                                       "MOTOSAKO"]),
    ("Ψυχαγωγία", False, ["VILLAGE CINEMAS", "VOLTA", "EUROLEAGUE", "HELLASMANIA", "BOOKING"]),
    ("Συνδρομές / Software", False, ["OPENAI", "COURSERA", "JETBRAINS", "UDEMY", "NETFLIX", "SPOTIFY", "GOOGLE",
                                     "APPLE.COM"]),
    ("Online αγορές", False, ["SKROUTZ", "SHEIN", "AMAZON", "PLAISIO", "PUBLIC", "IKEA", "MISTER PANTA",
                              "PANTA TA OLA"]),
    ("Μεταφορές σε λογαριασμούς", False, ["REVOLUT"]),
    (INCOME_OTHER, True, []),
    (EXPENSE_OTHER, False, []),
]
