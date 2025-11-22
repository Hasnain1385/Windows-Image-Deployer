# WindowsDeploy

A streamlined Windows image deployment utility that simplifies capturing, servicing, and deploying Windows images with an intuitive Python-powered workflow. Designed for IT administrators, lab/classroom environments, and systems engineers who need a reliable and repeatable way to prepare, customize, and deploy Windows at scale.


## Links
- GitHub repository: https://github.com/Hasnain1385/Windows-Image-Deployer
- YouTube channel: https://www.youtube.com/channel/UCFLQuLM-EcOm7r8ZtvITfKA?sub_confirmation=1

## Key Features
- Automated deployment workflows driven by Python tasks
- Clean separation of concerns across modules: app, system, tasks
- Simple launcher entry point for packaging or running locally
- Windows-centric tooling alignment (DISM/WinPE friendly)
- Packaged app support (spec file included) for distribution


## Project Structure
```
.
├─ app/
│  ├─ __init__.py
│  ├─ main.py          # Primary application entrypoint
│  ├─ system.py        # System helpers and Windows operations
│  └─ tasks.py         # Deployment and maintenance tasks
├─ assets/
│  └─ icon.ico         # App icon used for packaged builds
├─ launcher.py         # Convenience launcher
├─ requirements.txt    # Python dependencies
└─ README.md
```


## Prerequisites
- Windows 10/11
- Python 3.10+ installed and on PATH
- PowerShell and DISM available (included with Windows)
- Administrator privileges for deployment operations


## Installation
1. Clone the repository:
   git clone https://github.com/Hasnain1385/Windows-Image-Deployer
   cd Windows-Image-Deployer

2. (Recommended) Create and activate a virtual environment:
   python -m venv .venv
   .venv\\Scripts\\activate

3. Install dependencies:
   pip install -r requirements.txt


## Usage
You can run the application via the main module or the launcher script, depending on your workflow.

- Run using app main:
  python -m app.main

- Run using launcher:
  python launcher.py

Some tasks may require elevated permissions (Run as Administrator) to interact with DISM and system-level operations.


## Common Commands
- Install dependencies:
  pip install -r requirements.txt

- Lint (if you add a linter):
  ruff check .

- Run tests (if tests are added):
  pytest -q

- Package the application (example using PyInstaller):
  pyinstaller "Resources/Windows Image Deployment - Mirza Hasnain Baig.spec"

Note: Adjust packaging commands per your environment and chosen packager. The included .spec suggests PyInstaller was used.


## Configuration
- Modify tasks and flows in app/tasks.py
- Extend Windows helpers in app/system.py
- Adjust application orchestration/CLI in app/main.py
- Update icon and branding in assets/icon.ico


## Troubleshooting
- Ensure you are running the terminal as Administrator for operations that require DISM or access to protected directories.
- Verify Python version: python --version
- Validate that dependencies are installed: pip list
- For packaging, ensure the correct path and name of the .spec file and that PyInstaller is installed: pip install pyinstaller


## SEO-Optimized Overview
WindowsDeploy is a Windows image deployment tool for IT administrators and system integrators. It streamlines Windows imaging, customization, and deployment using Python automation. With support for DISM workflows and packaging via PyInstaller, WindowsDeploy enables fast, repeatable, and scalable Windows OS deployment across labs, classrooms, and enterprise environments. Keywords: Windows image deployment, DISM automation, Windows deployment tool, Windows imaging, Windows OS provisioning, Python deployment scripts, IT admin tools, WinPE compatible, enterprise imaging, classroom lab deployment.


## SEO-Optimized Feature Highlights
- Windows image capture and deployment automation using Python
- Integration-ready with DISM and WinPE workflows
- Modular architecture for maintainability and customization
- Scriptable tasks for repeatable provisioning pipelines
- Packaged application support for easy distribution in enterprise


## Contributing
1. Fork the repository
2. Create a feature branch: git checkout -b feature/your-feature
3. Commit your changes: git commit -m "feat: add your feature"
4. Push the branch: git push origin feature/your-feature
5. Open a Pull Request


## License
Add your license of choice (e.g., MIT, Apache 2.0) and include a LICENSE file in the repository root.
