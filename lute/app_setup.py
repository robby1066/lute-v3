"""
Main entry point.
"""

import os
from flask import Flask, render_template, redirect, flash

from lute.db import db
from lute.db.setup.main import setup_db
import lute.backup.service as backupservice
import lute.db.demo

from lute.models.book import Book
from lute.models.language import Language
from lute.models.setting import BackupSettings, UserSetting
from lute.book.stats import refresh_stats

from lute.book.routes import bp as book_bp
from lute.language.routes import bp as language_bp
from lute.term.routes import bp as term_bp
from lute.termtag.routes import bp as termtag_bp
from lute.read.routes import bp as read_bp
from lute.bing.routes import bp as bing_bp
from lute.userimage.routes import bp as userimage_bp
from lute.termimport.routes import bp as termimport_bp
from lute.term_parent_map.routes import bp as term_parent_map_bp
from lute.backup.routes import bp as backup_bp
from lute.dev_api.routes import bp as dev_api_bp
from lute.settings.routes import bp as settings_bp


def _setup_app_dirs(app_config):
    """
    App needs the data dir, backups, and other directories.
    """
    dp = app_config.datapath
    required_dirs = [
        { 'd': dp,
          'readme': "Lute data folder." },
        { 'd': os.path.join(dp, 'backups'),
          'readme': "Database backups created by Lute at app start." },
        { 'd': app_config.userimagespath,
          'readme': "User images.  Each subfolder is a language's ID." },
        { 'd': os.path.join(dp, 'custom_styles'),
          'readme': "User custom styles." }
    ]
    for rec in required_dirs:
        d = rec['d']
        if not os.path.exists(d):
            os.makedirs(d)
        readme = os.path.join(d, 'README.md')
        if not os.path.exists(readme):
            with open(readme, 'w', encoding='utf-8') as f:
                f.write(rec['readme'])


def _create_app(app_config, extra_config):
    """
    Create the app using the given configuration,
    and init the SqlAlchemy db.
    """

    app = Flask(__name__, instance_path=app_config.datapath)

    config = {
        'SECRET_KEY': 'some_secret',
        'DATABASE': app_config.dbfilename,
        'ENV': app_config.env,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{app_config.dbfilename}',

        'DATAPATH': app_config.datapath,

        # ref https://flask-sqlalchemy.palletsprojects.com/en/2.x/config/
        # Don't track mods.
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    }

    final_config = { **config, **extra_config }
    app.config.from_mapping(final_config)

    db.init_app(app)

    with app.app_context():
        db.create_all()
        UserSetting.load()

    app.db = db

    app.register_blueprint(language_bp)
    app.register_blueprint(book_bp)
    app.register_blueprint(term_bp)
    app.register_blueprint(termtag_bp)
    app.register_blueprint(read_bp)
    app.register_blueprint(bing_bp)
    app.register_blueprint(userimage_bp)
    app.register_blueprint(termimport_bp)
    app.register_blueprint(term_parent_map_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(dev_api_bp)
    app.register_blueprint(settings_bp)

    @app.route('/')
    def index():
        # Stop all other calculations if need to backup.
        bkp_settings = BackupSettings.get_backup_settings()
        if backupservice.should_run_auto_backup(bkp_settings):
            return redirect('/backup/backup', 302)

        is_demo = lute.db.demo.contains_demo_data()
        tutorial_book_id = lute.db.demo.tutorial_book_id()

        refresh_stats()

        return render_template(
            'index.html',
            dbname = app_config.dbname,
            datapath = app_config.datapath,
            tutorial_book_id = tutorial_book_id,
            have_books = len(db.session.query(Book).all()) > 0,
            have_languages = len(db.session.query(Language).all()) > 0,
            hide_home_link = True,
            is_production_data = not is_demo,

            backup_acknowledged = bkp_settings.is_acknowledged(),
            backup_enabled = (bkp_settings.backup_enabled == 'y'),
            backup_show_warning = bkp_settings.backup_warn,
            backup_warning_msg = backupservice.backup_warning(bkp_settings),
            backup_directory = bkp_settings.backup_dir,
            backup_last_display_date = bkp_settings.last_backup_display_date(),
        )

    @app.route('/wipe_database')
    def wipe_db():
        if lute.db.demo.contains_demo_data():
            lute.db.demo.delete_demo_data()
            flash('The database has been wiped clean.  Have fun!')
        return redirect('/', 302)

    return app


def init_db_and_app(app_config, extra_config = None):
    """
    Main entry point.  Calls dbsetup, and returns Flask app.

    Use extra_config to pass { 'TESTING': True } during unit tests.
    """

    _setup_app_dirs(app_config)
    setup_db(app_config)

    if extra_config is None:
        extra_config = {}
    app = _create_app(app_config, extra_config)

    return app