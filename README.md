# StudyBuddy: AI Study Assistant

An AI study assistant built with **LangGraph** for workflow orchestration and **Groq** (Llama 3.3 70B) for language model responses, with a **Streamlit** interface and **SQLite** storage.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-workflow-1C3C3C?style=flat)
![Groq](https://img.shields.io/badge/LLM-Groq%20Llama%203.3-F55036?style=flat)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)

## Architecture

| Layer | Technology |
|-------|-----------|
| Orchestration | LangGraph |
| LLM | Groq (Llama 3.3) |
| Storage | SQLite |
| UI | Streamlit |

See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

## Project structure

```
SttudyBuddy/
├── app_ui.py        # Streamlit interface
├── main.py          # Entry point
├── app/             # Application logic
├── infra/           # Infrastructure and storage
├── scripts/         # Utility scripts
├── tests/           # Test suite
├── tests_legacy/    # Previous tests, kept for reference
├── requirements.txt
└── .streamlit/      # Streamlit configuration
```

## Getting started

**Requirements:** Python 3.11+ and a free Groq API key from [console.groq.com](https://console.groq.com).

```bash
# 1. Clone
git clone https://github.com/abdullahhashmidev/SttudyBuddy.git
cd SttudyBuddy

# 2. Create and activate a virtual environment (Git Bash on Windows)
python -m venv .venv
source .venv/Scripts/activate
# macOS / Linux: source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your key
echo "GROQ_API_KEY=your_key_here" > .env
```

## Usage

```bash
# Command-line run
python main.py

# Web interface
streamlit run app_ui.py
```

## Notes

- Never commit `.env`. It is listed in `.gitignore`.
- The default branch is currently `hotfix/production-fixes-1790530870`. Merge it into `main` once the fixes are verified, then set `main` as the default branch.

## Author

**Abdullah Hashmi**, AI Engineer, Karachi, Pakistan · [GitHub](https://github.com/abdullahhashmidev)
