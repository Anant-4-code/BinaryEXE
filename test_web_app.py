import streamlit as st
import http.client
import json
from PIL import Image
import io
import base64

st.set_page_config(
    page_title="Handwriting Detection Test",
    page_icon="🖋️",
    layout="wide"
)

st.title("🖋️ Doctor's Handwriting Detection Test")
st.markdown("---")

def call_handwriting_api(image_bytes):
    """Call the handwriting OCR API to extract text from image"""
    try:
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
        
        return json.loads(data.decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}

def display_sample_images():
    """Display available sample images"""
    st.subheader("📸 Sample Images Available")
    
    sample_images = [
        "WhatsApp Image 2025-01-22 at 18.56.32_c1a2d136.jpg",
        "WhatsApp Image 2025-01-22 at 18.56.33_91195a07.jpg", 
        "WhatsApp Image 2025-01-22 at 18.56.33_f55ddbff.jpg"
    ]
    
    cols = st.columns(3)
    for i, img_name in enumerate(sample_images):
        with cols[i]:
            try:
                img = Image.open(img_name)
                st.image(img, caption=f"Sample {i+1}", use_column_width=True)
                if st.button(f"Use Sample {i+1}", key=f"sample_{i}"):
                    st.session_state.selected_image = img_name
                    st.rerun()
            except Exception as e:
                st.error(f"Could not load {img_name}: {e}")

# Main interface
col1, col2 = st.columns([1, 1])

with col1:
    st.header("📤 Upload Image")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Choose an image file",
        type=["jpg", "jpeg", "png", "webp"],
        help="Upload a doctor's handwriting image for OCR processing"
    )
    
    # Display sample images option
    st.markdown("---")
    display_sample_images()
    
    # Process button
    process_button = st.button(
        "🔍 Extract Text",
        type="primary",
        use_container_width=True,
        disabled=uploaded_file is None and "selected_image" not in st.session_state
    )

with col2:
    st.header("📝 Results")
    
    # Display uploaded or selected image
    if uploaded_file is not None:
        img = Image.open(uploaded_file)
        st.image(img, caption="Uploaded Image", use_column_width=True)
        image_bytes = uploaded_file.getvalue()
    elif "selected_image" in st.session_state:
        try:
            img = Image.open(st.session_state.selected_image)
            st.image(img, caption="Selected Sample Image", use_column_width=True)
            with open(st.session_state.selected_image, "rb") as f:
                image_bytes = f.read()
        except Exception as e:
            st.error(f"Error loading selected image: {e}")
            image_bytes = None
    else:
        st.info("Please upload an image or select a sample to begin.")
        image_bytes = None
    
    # Process the image when button is clicked
    if process_button and image_bytes:
        with st.spinner("🔄 Processing image..."):
            result = call_handwriting_api(image_bytes)
            
            if "error" in result:
                st.error(f"❌ Error: {result['error']}")
            else:
                detected_text = result.get("value", "")
                
                if detected_text:
                    st.success("✅ Text extracted successfully!")
                    
                    # Display extracted text
                    st.subheader("📄 Extracted Text:")
                    st.text_area(
                        "Detected handwriting:",
                        value=detected_text,
                        height=200,
                        disabled=True,
                        label_visibility="collapsed"
                    )
                    
                    # Copy to clipboard button
                    st.button(
                        "📋 Copy to Clipboard",
                        on_click=lambda: st.write("Text copied to clipboard!"),
                        help="Copy the extracted text"
                    )
                    
                    # Text statistics
                    with st.expander("📊 Text Statistics"):
                        st.write(f"**Character count:** {len(detected_text)}")
                        st.write(f"**Word count:** {len(detected_text.split())}")
                        st.write(f"**Line count:** {detected_text.count(chr(10)) + 1}")
                else:
                    st.warning("⚠️ No text was detected in the image. Please try with a clearer image.")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
        <p>🔧 This test interface uses the Pen-to-Print Handwriting OCR API</p>
        <p>For best results, use clear images with good lighting and legible handwriting</p>
    </div>
    """,
    unsafe_allow_html=True
)
