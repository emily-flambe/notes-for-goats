#!/bin/bash

# Colors for terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

ENV_EXAMPLE=".env.example"
ENV_FILE=".env"
ENV_TEMP=".env.temp"

echo -e "${GREEN}Creating .env file from .env.example...${NC}"

# Check if .env.example exists
if [ ! -f "$ENV_EXAMPLE" ]; then
    echo -e "${RED}Error: $ENV_EXAMPLE does not exist${NC}"
    exit 1
fi

# Create temp file with header
echo "# Environment variables for Notes for Goats" > "$ENV_TEMP"
echo "# Generated on $(date)" >> "$ENV_TEMP"
echo "" >> "$ENV_TEMP"

echo -e "${YELLOW}For each variable, enter a new value or press Enter to keep the default${NC}"
echo ""

# Helper function to generate a random Django secret key (alphanumeric only)
generate_django_secret_key() {
    python3 -c '
import random
import string
# Use only letters and digits, no special characters
chars = string.ascii_letters + string.digits
print("".join(random.choice(chars) for _ in range(50)))
'
}

# Use a simpler approach with explicit interactive prompting
grep -v "^#" "$ENV_EXAMPLE" | grep "=" | while IFS= read -r line; do
    # Extract key and value
    key=$(echo "$line" | cut -d= -f1)
    value=$(echo "$line" | cut -d= -f2-)
    
    # Special case for Django secret key
    if [ "$key" = "SECRET_KEY" ] || [ "$key" = "DJANGO_SECRET_KEY" ]; then
        echo -e -n "${GREEN}$key${NC} [default: ${YELLOW}generate a random secure key${NC}]: "
        read -r user_input </dev/tty
        
        if [ -z "$user_input" ]; then
            # Generate a random secret key
            random_key=$(generate_django_secret_key)
            echo "$key=$random_key" >> "$ENV_TEMP"
            echo -e "  Generated random key: ${YELLOW}$random_key${NC}"
        else
            echo "$key=$user_input" >> "$ENV_TEMP"
            echo -e "  Setting to: $user_input"
        fi
    else
        # Normal behavior for other variables
        echo -e -n "${GREEN}$key${NC} [default: ${YELLOW}$value${NC}]: "
        read -r user_input </dev/tty
        
        # Use default or new value
        if [ -z "$user_input" ]; then
            echo "$key=$value" >> "$ENV_TEMP"
            echo -e "  Using default: $value"
        else
            echo "$key=$user_input" >> "$ENV_TEMP"
            echo -e "  Setting to: $user_input"
        fi
    fi
    echo ""
done

# Replace .env with the new file
mv "$ENV_TEMP" "$ENV_FILE"

echo -e "${GREEN}Success! $ENV_FILE file has been created.${NC}"
echo "You can edit it manually at any time with your favorite editor." 