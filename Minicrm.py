# Flask CRM System for Organizations and Projects
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///minicrm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'
db = SQLAlchemy(app)

# Models
class Organization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    country = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    projects = db.relationship('Project', backref='organization', cascade="all, delete-orphan")

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    sector = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)

# Routes
@app.route('/')
def index():
    org_query = Organization.query.order_by(Organization.name)
    orgs = org_query.all()
    org_filter = request.args.get('org_filter', '')
    country_filter = request.args.get('country_filter', '')
    if org_filter:
        orgs = [o for o in orgs if org_filter.lower() in o.name.lower()]
    if country_filter:
        orgs = [o for o in orgs if country_filter.lower() in o.country.lower()]
    return render_template('index.html', organizations=orgs, org_filter=org_filter, country_filter=country_filter)

@app.route('/organization/add', methods=['GET', 'POST'])
def add_organization():
    if request.method == 'POST':
        name = request.form['name']
        country = request.form['country']
        if not name or not country:
            flash('Name and Country are required.', 'error')
            return redirect(url_for('add_organization'))
        org = Organization(name=name, country=country)
        db.session.add(org)
        db.session.commit()
        flash('Organization added!', 'success')
        return redirect(url_for('index'))
    return render_template('organization_form.html', org=None)

@app.route('/organization/<int:org_id>/edit', methods=['GET', 'POST'])
def edit_organization(org_id):
    org = Organization.query.get_or_404(org_id)
    if request.method == 'POST':
        org.name = request.form['name']
        org.country = request.form['country']
        db.session.commit()
        flash('Organization updated!', 'success')
        return redirect(url_for('index'))
    return render_template('organization_form.html', org=org)

@app.route('/organization/<int:org_id>/delete', methods=['POST'])
def delete_organization(org_id):
    org = Organization.query.get_or_404(org_id)
    db.session.delete(org)
    db.session.commit()
    flash('Organization deleted!', 'success')
    return redirect(url_for('index'))

@app.route('/project/add/<int:org_id>', methods=['GET', 'POST'])
def add_project(org_id):
    org = Organization.query.get_or_404(org_id)
    if request.method == 'POST':
        name = request.form['name']
        sector = request.form['sector']
        if not name or not sector:
            flash('Name and Sector are required.', 'error')
            return redirect(url_for('add_project', org_id=org_id))
        project = Project(name=name, sector=sector, organization_id=org_id)
        db.session.add(project)
        db.session.commit()
        flash('Project added!', 'success')
        return redirect(url_for('index'))
    return render_template('project_form.html', project=None, org=org)
