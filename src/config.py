"""Configuration module with smart defaults for CV Review Bot."""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Manager-configured (required)
BOT_TOKEN = os.getenv('BOT_TOKEN')
OPENROUTER_KEY = os.getenv('OPENROUTER_KEY')

if not BOT_TOKEN or not OPENROUTER_KEY:
    raise ValueError("BOT_TOKEN and OPENROUTER_KEY must be set in .env file")

# Optional: Restrict bot to specific Telegram user IDs (comma-separated)
# Example: MANAGER_IDS=123456789,987654321
# If not set, all users can use the bot

# Developer-configured (with defaults)
DATABASE_PATH = os.getenv('DATABASE_PATH', './data/reviews.db')
MAX_REPO_SIZE_MB = int(os.getenv('MAX_REPO_SIZE_MB', '100'))
ANALYSIS_TIMEOUT = int(os.getenv('ANALYSIS_TIMEOUT', '600'))
MAX_CONCURRENT = int(os.getenv('MAX_CONCURRENT', '3'))

# LLM Configuration
PRIMARY_MODEL = os.getenv('PRIMARY_MODEL', 'google/gemini-2.5-flash')
FALLBACK_MODEL = os.getenv('FALLBACK_MODEL', 'openai/gpt-5-mini')
MAX_TOKENS = int(os.getenv('MAX_TOKENS', '900000'))
TEMPERATURE = float(os.getenv('TEMPERATURE', '0.2'))

# Repository Processing
TEMP_DIR = os.getenv('TEMP_DIR', '/tmp/repos')
CLONE_TIMEOUT = int(os.getenv('CLONE_TIMEOUT', '60'))
CACHE_DURATION = int(os.getenv('CACHE_DURATION', '3600'))

# Manager IDs (comma-separated list)
MANAGER_IDS = os.getenv('MANAGER_IDS', '').split(',') if os.getenv('MANAGER_IDS') else []
MANAGER_IDS = [id.strip() for id in MANAGER_IDS if id.strip()]

# File Patterns for different roles - INCLUDE everything except useless files
BACKEND_PATTERNS = {
    'critical': ['**/*'],  # Get all files
    'important': [],
    'useful': [],
    'exclude': [
        # Package managers and dependencies
        'vendor/**',
        'node_modules/**',
        '.venv/**',
        'venv/**',
        'env/**',
        '__pycache__/**',
        '*.pyc',
        '*.pyo',
        '*.pyd',
        '.Python',
        'pip-log.txt',
        'pip-delete-this-directory.txt',
        
        # Build outputs
        'build/**',
        'dist/**',
        'target/**',
        'bin/**',
        'obj/**',
        'out/**',
        '*.egg-info/**',
        
        # Version control
        '.git/**',
        '.svn/**',
        '.hg/**',
        
        # IDE and editor files
        '.idea/**',
        '.vscode/**',
        '*.swp',
        '*.swo',
        '*~',
        '.DS_Store',
        'Thumbs.db',
        
        # Compiled files
        '*.exe',
        '*.dll',
        '*.so',
        '*.dylib',
        '*.a',
        '*.o',
        '*.class',
        '*.jar',
        '*.war',
        '*.ear',
        
        # Logs and databases
        '*.log',
        '*.sqlite',
        '*.db',
        
        # Media files (usually not code)
        '*.png',
        '*.jpg',
        '*.jpeg',
        '*.gif',
        '*.ico',
        '*.pdf',
        '*.mp4',
        '*.mp3',
        '*.wav',
        '*.avi',
        
        # Archives
        '*.zip',
        '*.tar',
        '*.gz',
        '*.rar',
        '*.7z',
        
        # Large data files
        '*.csv',
        '*.parquet',
        '*.feather',
        '*.h5',
        '*.hdf5'
    ]
}

FRONTEND_PATTERNS = {
    'critical': ['**/*'],  # Get all files
    'important': [],
    'useful': [],
    'exclude': [
        # Package managers and dependencies
        'node_modules/**',
        'bower_components/**',
        'jspm_packages/**',
        '.pnp/**',
        '.pnp.js',
        'package-lock.json',
        'yarn.lock',
        'pnpm-lock.yaml',
        
        # Build outputs
        'build/**',
        'dist/**',
        'out/**',
        '.next/**',
        '.nuxt/**',
        '.cache/**',
        'coverage/**',
        '.parcel-cache/**',
        
        # Version control
        '.git/**',
        '.svn/**',
        '.hg/**',
        
        # IDE and editor files
        '.idea/**',
        '.vscode/**',
        '*.swp',
        '*.swo',
        '*~',
        '.DS_Store',
        'Thumbs.db',
        
        # Font files (binary)
        '*.woff',
        '*.woff2',
        '*.ttf',
        '*.eot',
        '*.otf',
        
        # Media files
        '*.png',
        '*.jpg',
        '*.jpeg',
        '*.gif',
        '*.svg',
        '*.ico',
        '*.webp',
        '*.mp4',
        '*.mp3',
        '*.wav',
        '*.avi',
        
        # Archives
        '*.zip',
        '*.tar',
        '*.gz',
        '*.rar',
        '*.7z',
        
        # Other binary files
        '*.pdf',
        '*.exe',
        '*.dll',
        '*.so',
        '*.dylib'
    ]
}