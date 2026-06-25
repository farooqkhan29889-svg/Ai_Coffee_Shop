import firebase_admin

# Delete any existing app
if firebase_admin._apps:
    firebase_admin.delete_app(firebase_admin._apps[0])

# Reinitialize fresh
cred = credentials.Certificate(os.getenv("FIREBASE_KEY_FILE"))
firebase_admin.initialize_app(cred)
db = firestore.client()