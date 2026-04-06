import streamlit as st
import http.client
import json
from PIL import Image
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import google.generativeai as genai
import random
import time

genai.configure(api_key="AIzaSyArFsF8XTEyuPDbQhtvGjZfygziLN6RF7o")
USER_DB = "users.json"

def load_users():
    if os.path.exists(USER_DB):
        with open(USER_DB, "r") as file:
            return json.load(file)
    return {}

def save_users(users):
    with open(USER_DB, "w") as file:
        json.dump(users, file, indent=4)

def register_user():
    st.subheader("Register")
    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    confirm_password = st.text_input("Confirm Password", type="password")

    if st.button("Register"):
        if not username or not email or not password:
            st.error("Please fill out all fields.")
        elif password != confirm_password:
            st.error("Passwords do not match.")
        else:
            users = load_users()
            if username in users:
                st.error("Username already exists.")
            else:
                users[username] = {"email": email, "password": password, "trial_count": 10}
                save_users(users)
                st.success("Registration successful! Please log in.")
def save_trial_count(username, count):
    users = load_users()
    if username in users:
        users[username]["trial_count"] = count
        save_users(users)

def login_user():
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        users = load_users()
        if username in users and users[username]["password"] == password:
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
            st.session_state["email"] = users[username]["email"]
            st.success(f"Welcome {username}!")
        else:
            st.error("Invalid username or password.")

def send_email(to_email, subject, body):
    sender_email = "firstname7302@gmail.com"  # Replace with your email
    sender_password = "trem jgiq fptt wjqg"  # Replace with your email password or app password

    # Set up the email
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject

    # Add the body
    msg.attach(MIMEText(body, 'plain'))

    try:
        # Connect to the server and send the email
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

# Symptom-based disease identification
def identify_disease(symptoms):
    #genai.configure(api_key="YOUR_API_KEY")  # Replace with your actual API key
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    try:
        response = model.generate_content(f"Identify possible diseases based on symptoms: {', '.join(symptoms)}")
        diseases = response.text
    except Exception as e:
        st.error(f"Error with Gemini API: {e}")
        diseases = "Could not fetch diseases. Please try again."

    return diseases

# Extract drugs from summarized text
def extract_drugs_from_summary(summary):
  #  genai.configure(api_key="YOUR_API_KEY")  # Replace with your actual API key
    model = genai.GenerativeModel("gemini-1.5-flash")

    try:
        response = model.generate_content(f"Extract medication names from the following text: {summary}")
        drugs = response.text.split(',')  # Assuming the API returns a comma-separated list of drugs
        return [drug.strip() for drug in drugs]
    except Exception as e:
        st.error(f"Error with Gemini API: {e}")
        return []

# Drug compatibility analysis
def analyze_drug(drugs):
   # genai.configure(api_key="YOUR_API_KEY")  # Replace with your actual API key
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    try:
        response = model.generate_content(f"Analyze compatibility and alternatives for the following drugs: {', '.join(drugs)}")
        drug_info = response.text
    except Exception as e:
        st.error(f"Error with Gemini API: {e}")
        drug_info = "Could not fetch drug compatibility and alternatives. Please try again."

    return drug_info

@st.cache_resource
def text_summary_with_gemini(text):
   # genai.configure(api_key="YOUR_API_KEY")  # Replace with your actual API key
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    try:
        response = model.generate_content(f"Summarize the following text extracted from a prescription: {text}")
        summary = response.text
    except Exception as e:
        st.error(f"Error with Gemini API: {e}")
        summary = "Could not generate summary. Please try again."

    return summary

# Pricing and subscription module
def subscription_module():
    st.title("Subscription Plans")
    st.write("Your free trial is over. You need to subscribe to continue using the service.")
    st.write("### Subscription Plans:")
    st.write("- **Monthly**: $10 - Access all features for one month.")
    st.write("- **3 Months**: $25 - Save 15%.")
    st.write("- **6 Months**: $45 - Save 25%.")
    st.write("- **Yearly**: $80 - Save 33%.")
    if st.button("Buy Now"):
        st.success("Redirecting to payment page... (This is a dummy page)")

# Emergency Medical Backup System
def emergency_backup_system(diseases):
    #genai.configure(api_key="YOUR_API_KEY")  # Replace with your actual API key
    model = genai.GenerativeModel("gemini-1.5-flash")

    try:
        response = model.generate_content(f"Analyze emergency risk for diseases: {', '.join(diseases)}")
        risk_analysis = response.text
        if "high risk" in risk_analysis.lower():
            st.warning("High-risk disease detected! Sending an alert to nearby hospitals.")
            send_email("hospital@example.com", "Emergency Alert", f"Emergency alert for high-risk disease: {', '.join(diseases)}")
        else:
            st.info("No immediate emergency detected.")
    except Exception as e:
        st.error(f"Error with Gemini API: {e}")



def call_handwriting_api(image_bytes):
    conn = http.client.HTTPSConnection("pen-to-print-handwriting-ocr.p.rapidapi.com")

    boundary = "----011000010111000001101001"
    
    payload = (
        f"--{boundary}\r\n"
        "Content-Disposition: form-data; name=\"srcImg\"; filename=\"image.jpg\"\r\n"
        "Content-Type: image/jpeg\r\n\r\n"
    ).encode("utf-8") + image_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
    
    headers = {
        'x-rapidapi-key': "c269328ea7msh57906c6d25588c4p108f2ejsn7def9222465a",
        'x-rapidapi-host': "pen-to-print-handwriting-ocr.p.rapidapi.com",
        'Content-Type': f"multipart/form-data; boundary={boundary}"
    }

    conn.request("POST", "/recognize/", payload, headers)
    res = conn.getresponse()
    data = res.read()
    
    return data.decode("utf-8")

# Logout functionality
def logout():
    if st.sidebar.button("Logout"):
        st.session_state["logged_in"] = False
        st.experimental_rerun()
def save_trial_count(username, count):
    users = load_users()
    if username in users:
        users[username]["trial_count"] = count
        save_users(users)
# Sidebar Layout
def sidebar():
    st.sidebar.header("User Dashboard")

    if "logged_in" not in st.session_state or not st.session_state.get("logged_in"):
        auth_option = st.sidebar.radio("", ["Login", "Register"])
        if auth_option == "Login":
            login_user()
        elif auth_option == "Register":
            register_user()
    else:
        st.sidebar.success(f"Logged in as {st.session_state['username']}")
        st.sidebar.markdown(f"**Free Trials Left**: {st.session_state['trial_count']}")
        if st.sidebar.button("Logout"):
            save_trial_count(st.session_state["username"], st.session_state["trial_count"])
            st.session_state["logged_in"] = False
            st.rerun()
        st.sidebar.subheader("Emergency Actions")
        if st.sidebar.button("SOS - Emergency Alert"):
            with st.sidebar.expander("Disclaimer", expanded=True):
                st.warning("By clicking OK, you agree to bear ambulance charges if this is a false alarm. Proceed only in case of a real emergency.")
                if st.button("OK and Confirm Emergency Alert", key="sos_confirm"):
                    send_email("hospital@example.com", "Manual SOS Alert", "An emergency alert has been triggered manually.")
                    st.success("Emergency alert sent to nearby hospitals.")


# Main application function
def main():
    st.title("Doctor's Handwriting OCR and Summarization")


        # Initialize session state variables
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
    if "username" not in st.session_state:
        st.session_state["username"] = None
    if "email" not in st.session_state:
        st.session_state["email"] = None
    if "trial_count" not in st.session_state:
        st.session_state["trial_count"] = 10

    sidebar()
    
    
    if "logged_in" in st.session_state and st.session_state.get("logged_in"):

        if st.session_state["trial_count"] <= 0:
            subscription_module()
            return

        # Tabs for better UI organization
        tab1, tab2, tab3, tab4 = st.tabs(["OCR & Summarization", "Disease Identification", "Drug Analysis", "Emergency Features"])

        with tab1:
            st.header("OCR & Summarization")
            st.image(r"C:\Users\Dell\OneDrive\Desktop\Doctor hand writting\img\doc.jpeg", caption="Upload handwriting to detect and summarize")

            uploaded_file = st.file_uploader("Upload a handwriting image", type=["jpg", "jpeg", "png", "webp"])

            if uploaded_file is not None:
                img = Image.open(uploaded_file)
                st.image(img, caption="Uploaded Image", use_column_width=True)

                img_bytes = uploaded_file.getvalue()

                st.write("Processing image...")
                result = call_handwriting_api(img_bytes)
                result_data = json.loads(result)

                detected_text = result_data.get("value", "No text detected.")
                st.markdown(f"### Detected Text:")
                st.code(detected_text, language='text')

                st.write("Summarizing detected text...")
                if detected_text.strip():
                    summary = text_summary_with_gemini(detected_text)
                    st.markdown(f"### Summarized Text:")
                    st.code(summary, language='text')

                    drugs_from_summary = extract_drugs_from_summary(summary)

                    st.write("Send summarized text to your email")
                    user_email = st.session_state.get("email", "")
                    if st.button("Send Email"):
                        if send_email(user_email, "Summarized Text", summary):
                            st.success("Email sent successfully!")
                        else:
                            st.error("Failed to send email.")

        with tab2:
            st.header("Disease Identification")
            st.write("Automatically detect diseases from summarized text or enter symptoms manually.")

            method = st.radio("How do you want to provide symptoms?", ("From Summarized Text", "Manual Entry"))

            diseases = []
            if method == "From Summarized Text":
                if 'summary' in locals():
                    symptoms_list = summary.lower().split()
                    diseases = identify_disease(symptoms_list)
                    st.write("### Possible Diseases:")
                    st.write(diseases)
                else:
                    st.warning("No summary available. Please complete the summarization step first.")

            elif method == "Manual Entry":
                symptoms_input = st.text_area("Enter symptoms separated by commas", placeholder="e.g., fever, headache")
                if st.button("Identify Diseases"):
                    symptoms_list = [symptom.strip() for symptom in symptoms_input.split(",")]
                    diseases = identify_disease(symptoms_list)
                    st.write("### Possible Diseases:")
                    st.write(diseases)

        with tab3:
            st.header("Drug Analysis")
            st.write("Analyze drug compatibility and alternatives.")

            drug_source = st.radio("Choose input method for drugs:", ("Extracted from Summary", "Based on Diseases", "Manual Entry"))

            if drug_source == "Extracted from Summary":
                if 'drugs_from_summary' in locals() and drugs_from_summary:
                    st.write("### Drugs Extracted from Summary:")
                    st.write(", ".join(drugs_from_summary))
                    drug_info = analyze_drug(drugs_from_summary)
                    st.write("### Drug Information:")
                    st.write(drug_info)
                else:
                    st.warning("No drugs extracted. Please complete the summarization step first.")

            elif drug_source == "Based on Diseases":
                if diseases:
                    st.write("### Drugs Suggested for Detected Diseases:")
                    drugs_for_diseases = extract_drugs_from_summary(", ".join(diseases))
                    st.write(", ".join(drugs_for_diseases))
                    drug_info = analyze_drug(drugs_for_diseases)
                    st.write("### Drug Information:")
                    st.write(drug_info)
                else:
                    st.warning("No diseases detected. Please complete the disease identification step first.")

            elif drug_source == "Manual Entry":
                drugs_input = st.text_area("Enter drug names separated by commas", placeholder="e.g., Paracetamol, Ibuprofen")
                if st.button("Analyze Drugs"):
                    drugs_list = [drug.strip() for drug in drugs_input.split(",")]
                    drug_info = analyze_drug(drugs_list)
                    st.write("### Drug Information:")
                    st.write(drug_info)

        with tab4:
            st.header("Emergency Features")

            st.subheader("Automatic Emergency Backup System")
            if diseases:
                emergency_backup_system(diseases)
            else:
                st.warning("No detected diseases to analyze for emergency backup.")
            
        st.session_state["trial_count"] -= 1  # Example diseases for demo

if __name__ == "__main__":
    main()
