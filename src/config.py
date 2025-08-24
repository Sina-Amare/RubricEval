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
MANAGER_IDS = os.getenv('MANAGER_IDS', '')

# Developer-configured (with defaults)
DATABASE_PATH = os.getenv('DATABASE_PATH', './data/reviews.db')
MAX_REPO_SIZE_MB = int(os.getenv('MAX_REPO_SIZE_MB', '100'))
ANALYSIS_TIMEOUT = int(os.getenv('ANALYSIS_TIMEOUT', '600'))
MAX_CONCURRENT = int(os.getenv('MAX_CONCURRENT', '3'))

# LLM Configuration
PRIMARY_MODEL = os.getenv('PRIMARY_MODEL', 'google/gemini-flash-1.5-8b')
FALLBACK_MODEL = os.getenv('FALLBACK_MODEL', 'openai/gpt-4-turbo-preview')
MAX_TOKENS = int(os.getenv('MAX_TOKENS', '900000'))
TEMPERATURE = float(os.getenv('TEMPERATURE', '0.2'))

# Repository Processing
TEMP_DIR = os.getenv('TEMP_DIR', '/tmp/repos')
CLONE_TIMEOUT = int(os.getenv('CLONE_TIMEOUT', '60'))
CACHE_DURATION = int(os.getenv('CACHE_DURATION', '3600'))

# Manager IDs (comma-separated list)
MANAGER_IDS = os.getenv('MANAGER_IDS', '').split(',') if os.getenv('MANAGER_IDS') else []
MANAGER_IDS = [id.strip() for id in MANAGER_IDS if id.strip()]

# File Patterns for different roles
BACKEND_PATTERNS = {
    'critical': [
        'main.go', 
        'cmd/**/*.go', 
        'handler/**/*.go', 
        'handlers/**/*.go',
        'api/**/*.go',
        'server/**/*.go'
    ],
    'important': [
        'service/**/*.go',
        'services/**/*.go', 
        'model/**/*.go',
        'models/**/*.go',
        'repository/**/*.go',
        'repositories/**/*.go',
        'pkg/**/*.go',
        'internal/**/*.go'
    ],
    'useful': [
        '**/*_test.go', 
        'go.mod', 
        'go.sum', 
        'README.md',
        'Dockerfile',
        '.env.example'
    ],
    'exclude': [
        'vendor/**', 
        '.git/**', 
        '**/*.pb.go',
        'bin/**',
        'dist/**'
    ]
}

FRONTEND_PATTERNS = {
    'critical': [
        'src/App.*',
        'src/index.*',
        'src/main.*',
        'pages/**/*',
        'app/**/*'
    ],
    'important': [
        'components/**/*',
        'src/components/**/*',
        'services/**/*',
        'src/services/**/*',
        'hooks/**/*',
        'src/hooks/**/*',
        'utils/**/*',
        'src/utils/**/*'
    ],
    'useful': [
        '**/*.test.*',
        '**/*.spec.*',
        'package.json',
        '*.config.js',
        '*.config.ts',
        'tsconfig.json',
        'README.md'
    ],
    'exclude': [
        'node_modules/**',
        'build/**',
        'dist/**',
        '.git/**',
        'coverage/**',
        '.next/**',
        'out/**'
    ]
}