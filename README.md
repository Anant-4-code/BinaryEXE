# BinaryEXE

A comprehensive web application built with Streamlit that provides user authentication, AI-powered services, and email functionality.

## Features

- **User Authentication**: Complete registration and login system with trial-based access
- **AI Integration**: Powered by Google Generative AI for intelligent responses
- **Email Services**: Built-in email functionality with file attachment support
- **Image Processing**: PIL-based image handling capabilities
- **Database Management**: JSON-based user data storage

## Project Structure

```
BinaryEXE/
├── app3.py                 # Main Streamlit application
├── mediscript_ai/          # Additional application modules
│   ├── app/               # Core application components
│   ├── mediscript.db      # Database file
│   ├── tests/             # Test files
│   └── uploads/           # File upload directory
├── requirements.txt        # Python dependencies
├── users.json            # User database
├── test_web_app.py       # Test suite
└── README.md             # This file
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Anant-4-code/BinaryEXE.git
cd BinaryEXE
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1  # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Dependencies

- **streamlit==1.28.1** - Web application framework
- **Pillow==10.0.1** - Image processing library
- **requests==2.31.0** - HTTP library for API calls
- **google-generativeai==0.3.2** - Google AI API client

## Usage

1. Run the application:
```bash
streamlit run app3.py
```

2. Open your browser and navigate to the provided local URL (usually `http://localhost:8501`)

3. Register a new account or log in with existing credentials

## Configuration

The application uses Google Generative AI. Make sure to:
- Set up your Google AI API key
- Configure the API key in the application (currently hardcoded in `app3.py`)

## User System

- Each user gets 10 trial uses upon registration
- User data is stored in `users.json`
- Authentication includes username, email, and password validation

## Testing

Run the test suite:
```bash
python test_web_app.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is open source and available under the MIT License.
