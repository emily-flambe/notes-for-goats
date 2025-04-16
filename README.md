# Notes for Goats

A personal note-taking application designed for serious professionals (this could be you!) to organize structured notes about people, projects, and daily events.

## AI disclosure

This app was vibe-coded _par excellence_ with extremely heavy assistance from claude-3.7-sonnet.

I have no plans to productionize or monetize this application. Honestly, who has the time?

## Purpose

Notes for Goats solves the challenge of keeping structured, searchable notes on professional activities while maintaining data privacy through local storage. Unlike cloud-based solutions, this system gives you:

- Complete data ownership with local SQLite storage
- Entity-based organization (people, projects, teams)
- Integrated journaling with entity tagging via #hashtags
- Google Calendar event import capability
- Structured search and relationship browsing

Built by engineers for engineers, it emphasizes quick note-taking while automatically organizing information by entities.

## Getting Started

### Prerequisites

- Python 3.8+ 
- Django 4.2+
- (Optional) Google Calendar API credentials

### Installation

1. Clone the repository
```bash
git clone https://github.com/yourusername/notes-for-goats.git
cd notes-for-goats
```

2. Create and activate a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Set up the database
```bash
python manage.py migrate
```

5. Create an admin user
```bash
python manage.py createsuperuser
```

6. Run the development server
```bash
python manage.py runserver
```

7. Access the application
   - Main app: http://127.0.0.1:8000/
   - Admin interface: http://127.0.0.1:8000/admin/

## Usage

### Core Functionality

1. **Creating Entities**
   - Navigate to "Entities" and click "New Entity"
   - Choose the type: Person, Project, or Team
   - Enter details and save

2. **Journal Entries**
   - Navigate to "Journal" and click "New Journal Entry"
   - Use #hashtags to reference entities (e.g., "Meeting with #Alice about #ProjectX")
   - Entities will be automatically linked if they exist in the system

3. **Entity References**
   - Click on any entity to see all journal entries that reference it
   - Explore relationships between people, projects, and teams

4. **Admin Interface**
   - Access powerful data management tools via the admin console
   - Bulk edit, search, and organize your data

### Google Calendar Integration (Future)

The system is designed to integrate with Google Calendar to:
- Import your daily events
- Generate journal templates pre-populated with meetings
- Link notes directly to calendar events

## Data Backup

Your data is stored in a SQLite database (`db.sqlite3`). To back up your data:

1. Stop the application if it's running
2. Copy the `db.sqlite3` file to a secure location
3. For a more portable backup, use the export command:
```bash
python manage.py export_data
```

## Project Structure

```
notes_for_goats/
├── notes_for_goats/ # Workspace settings
│ ├── settings.py # Configuration
│ ├── urls.py # URL routing
│ ├── wsgi.py # WSGI configuration
├── notekeeper/ # Main application
│ ├── models.py # Data models
│ ├── views.py # View logic
│ ├── forms.py # Form definitions
│ ├── admin.py # Admin interface
│ ├── urls.py # URL patterns
│ ├── templates/ # HTML templates
│ │ └── notekeeper/ # App-specific templates
│ ├── management/ # Custom commands
│ │ └── commands/ # Management commands
├── manage.py # Django management script
└── db.sqlite3 # SQLite database
```

## Design Decisions

### Why Django?

Django was chosen for several reasons:
1. **Rapid Development**: Built-in admin, ORM, and templating
2. **Batteries Included**: Authentication, forms, and security
3. **Maintainable**: Clear MVC-like pattern with Django's MVT
4. **Local First**: Easy setup with SQLite for local data storage
5. **Python Ecosystem**: Access to libraries for calendar integration, data processing

### Why SQLite?

SQLite provides the perfect balance for a personal tool:
1. **Zero Configuration**: No database server required
2. **Portability**: Single file database that can be backed up anywhere
3. **Reliability**: ACID-compliant, trusted in mission-critical applications
4. **Local First**: Prioritizes data ownership and privacy

### Entity-Centered Design

The app revolves around the concept of entities (people, projects, teams):
1. **Centralized Information**: Each entity becomes a hub for related information
2. **Intuitive Tagging**: Natural writing with #hashtags maintains flow while creating structure
3. **Relationship Exploration**: Navigate between related entries and entities
4. **Flexible Journaling**: Combines the freedom of free-form writing with the structure of a database

### Template-Based UI vs API+SPA

We chose Django templates for the UI because:
1. **Simplicity**: Faster development with fewer moving parts
2. **Cohesiveness**: Unified backend and frontend development
3. **Focus on Functionality**: Emphasizes core note-taking capabilities over UI sophistication
4. **Future Extensibility**: API endpoints can be added later if a more dynamic UI is desired

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Inspired by tools like Obsidian, Notion, and Day One
- Built to solve the real-world problems of engineering leaders

---

*Notes for Goats: Because even leaders need to keep track of their flock* 🐐📝