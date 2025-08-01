# Flask CRM System for Organizations and Projects
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import io
import csv
import math
import pandas as pd

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///minicrm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'
db = SQLAlchemy(app)

# Models
class Country(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

class Sector(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

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

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entity = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    action = db.Column(db.String(20))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text)

# Helper: log audit
def log_audit(entity, entity_id, action, details=None):
    log = AuditLog(entity=entity, entity_id=entity_id, action=action, details=details)
    db.session.add(log)
    db.session.commit()

# Pagination helper
def paginate(query, page, per_page):
    total = query.count()
    items = query.offset((page-1)*per_page).limit(per_page).all()
    pages = math.ceil(total / per_page)
    return items, total, pages

@app.route('/')
def index():
    org_query = Organization.query.order_by(Organization.name)
    org_filter = request.args.get('org_filter', '')
    country_filter = request.args.get('country_filter', '')
    page = int(request.args.get('page', 1))
    per_page = 10
    if org_filter:
        org_query = org_query.filter(Organization.name.ilike(f"%{org_filter}%"))
    if country_filter:
        org_query = org_query.filter(Organization.country.ilike(f"%{country_filter}%"))
    orgs, total, pages = paginate(org_query, page, per_page)
    return render_template('index.html', organizations=orgs, org_filter=org_filter, country_filter=country_filter, page=page, pages=pages, total=total)

@app.route('/projects')
def projects():
    project_query = Project.query.order_by(Project.created_at.desc())
    name_filter = request.args.get('name_filter', '')
    sector_filter = request.args.get('sector_filter', '')
    org_filter = request.args.get('org_filter', '')
    page = int(request.args.get('page', 1))
    per_page = 10
    if name_filter:
        project_query = project_query.filter(Project.name.ilike(f"%{name_filter}%"))
    if sector_filter:
        project_query = project_query.filter(Project.sector.ilike(f"%{sector_filter}%"))
    if org_filter:
        project_query = project_query.join(Organization).filter(Organization.name.ilike(f"%{org_filter}%"))
    projects, total, pages = paginate(project_query, page, per_page)
    orgs = Organization.query.order_by(Organization.name).all()
    return render_template('projects.html', projects=projects, orgs=orgs, name_filter=name_filter, sector_filter=sector_filter, org_filter=org_filter, page=page, pages=pages, total=total)

@app.route('/analytics')
def analytics():
    org_filter = request.args.get('org_filter', '')
    project_filter = request.args.get('project_filter', '')
    sector_filter = request.args.get('sector_filter', '')
    org_query = Organization.query
    project_query = Project.query
    if org_filter:
        org_query = org_query.filter(Organization.name.ilike(f"%{org_filter}%"))
        project_query = project_query.join(Organization).filter(Organization.name.ilike(f"%{org_filter}%"))
    if project_filter:
        project_query = project_query.filter(Project.name.ilike(f"%{project_filter}%"))
    if sector_filter:
        project_query = project_query.filter(Project.sector.ilike(f"%{sector_filter}%"))
    total_orgs = org_query.count()
    total_projects = project_query.count()
    sector_counts = {s: c for s, c in db.session.query(Project.sector, db.func.count(Project.id)).group_by(Project.sector)}
    country_counts = {c: cnt for c, cnt in db.session.query(Organization.country, db.func.count(Project.id)).join(Project, Project.organization_id == Organization.id).group_by(Organization.country)}
    return render_template('analytics.html', org_filter=org_filter, project_filter=project_filter, sector_filter=sector_filter, total_orgs=total_orgs, total_projects=total_projects, sector_counts=sector_counts, country_counts=country_counts)

@app.route('/organization/bulk_upload', methods=['GET', 'POST'])
def bulk_upload_organizations():
    if request.method == 'POST':
        file = request.files['file']
        if file and file.filename.endswith('.csv'):
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            reader = csv.DictReader(stream)
            for row in reader:
                if row.get('name') and row.get('country'):
                    # Add country to master if not exists
                    country_name = row['country'].strip()
                    if country_name and not Country.query.filter_by(name=country_name).first():
                        db.session.add(Country(name=country_name))
                    org = Organization(name=row['name'], country=country_name)
                    db.session.add(org)
            db.session.commit()
            flash('Bulk upload successful!', 'success')
            return redirect(url_for('index'))
        flash('Please upload a valid CSV file.', 'error')
    return render_template('bulk_upload.html', entity='Organization')

@app.route('/project/bulk_upload', methods=['GET', 'POST'])
def bulk_upload_projects():
    orgs = Organization.query.all()
    if request.method == 'POST':
        file = request.files['file']
        if file and file.filename.endswith('.csv'):
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            reader = csv.DictReader(stream)
            for row in reader:
                org = Organization.query.filter_by(name=row.get('organization')).first()
                sector_name = row.get('sector', '').strip()
                # Add sector to master if not exists
                if sector_name and not Sector.query.filter_by(name=sector_name).first():
                    db.session.add(Sector(name=sector_name))
                if row.get('name') and sector_name and org:
                    project = Project(name=row['name'], sector=sector_name, organization_id=org.id)
                    db.session.add(project)
            db.session.commit()
            flash('Bulk upload successful!', 'success')
            return redirect(url_for('projects'))
        flash('Please upload a valid CSV file.', 'error')
    return render_template('bulk_upload.html', entity='Project', orgs=orgs)

@app.route('/organization/export')
def export_organizations():
    orgs = Organization.query.all()
    df = pd.DataFrame([{ 'Name': o.name, 'Country': o.country, 'Created At': o.created_at } for o in orgs])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Organizations')
    output.seek(0)
    return send_file(output, download_name='organizations.xlsx', as_attachment=True)

@app.route('/project/export')
def export_projects():
    projects = Project.query.all()
    df = pd.DataFrame([{ 'Name': p.name, 'Sector': p.sector, 'Organization': p.organization.name if p.organization else '', 'Created At': p.created_at } for p in projects])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Projects')
    output.seek(0)
    return send_file(output, download_name='projects.xlsx', as_attachment=True)

@app.route('/organization/add', methods=['GET', 'POST'])
def add_organization():
    countries = Country.query.order_by(Country.name).all()
    if request.method == 'POST':
        name = request.form['name']
        country = request.form['country']
        if not name or not country:
            flash('Name and Country are required.', 'error')
            return redirect(url_for('add_organization'))
        org = Organization(name=name, country=country)
        db.session.add(org)
        db.session.commit()
        log_audit('Organization', org.id, 'add', f'Name: {name}, Country: {country}')
        flash('Organization added!', 'success')
        return redirect(url_for('index'))
    return render_template('organization_form.html', org=None, countries=countries)

@app.route('/organization/<int:org_id>/edit', methods=['GET', 'POST'])
def edit_organization(org_id):
    org = Organization.query.get_or_404(org_id)
    countries = Country.query.order_by(Country.name).all()
    if request.method == 'POST':
        org.name = request.form['name']
        org.country = request.form['country']
        db.session.commit()
        log_audit('Organization', org.id, 'edit', f'Name: {org.name}, Country: {org.country}')
        flash('Organization updated!', 'success')
        return redirect(url_for('index'))
    return render_template('organization_form.html', org=org, countries=countries)

@app.route('/organization/<int:org_id>/delete', methods=['POST'])
def delete_organization(org_id):
    org = Organization.query.get_or_404(org_id)
    db.session.delete(org)
    db.session.commit()
    log_audit('Organization', org.id, 'delete', f'Name: {org.name}, Country: {org.country}')
    flash('Organization deleted!', 'success')
    return redirect(url_for('index'))

@app.route('/project/add', methods=['GET', 'POST'])
def add_project():
    orgs = Organization.query.order_by(Organization.name).all()
    sectors = Sector.query.order_by(Sector.name).all()
    if request.method == 'POST':
        name = request.form['name']
        sector = request.form['sector']
        organization_id = request.form['organization_id']
        if not name or not sector or not organization_id:
            flash('Name, Sector, and Organization are required.', 'error')
            return redirect(url_for('add_project'))
        project = Project(name=name, sector=sector, organization_id=organization_id)
        db.session.add(project)
        db.session.commit()
        log_audit('Project', project.id, 'add', f'Name: {name}, Sector: {sector}, OrgID: {organization_id}')
        flash('Project added!', 'success')
        return redirect(url_for('projects'))
    return render_template('project_form.html', project=None, orgs=orgs, sectors=sectors)

@app.route('/project/<int:project_id>/edit', methods=['GET', 'POST'])
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    orgs = Organization.query.order_by(Organization.name).all()
    sectors = Sector.query.order_by(Sector.name).all()
    if request.method == 'POST':
        project.name = request.form['name']
        project.sector = request.form['sector']
        project.organization_id = int(request.form['organization_id'])
        db.session.commit()
        log_audit('Project', project.id, 'edit', f'Name: {project.name}, Sector: {project.sector}, OrgID: {project.organization_id}')
        flash('Project updated!', 'success')
        return redirect(url_for('projects'))
    return render_template('project_form.html', project=project, orgs=orgs, sectors=sectors)

@app.route('/project/<int:project_id>/delete', methods=['POST'])
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    log_audit('Project', project.id, 'delete', f'Name: {project.name}, Sector: {project.sector}, OrgID: {project.organization_id}')
    flash('Project deleted!', 'success')
    return redirect(url_for('projects'))

@app.route('/masters', methods=['GET'])
def masters():
    countries = Country.query.order_by(Country.name).all()
    sectors = Sector.query.order_by(Sector.name).all()
    return render_template('masters.html', countries=countries, sectors=sectors)

@app.route('/masters/country/add', methods=['POST'])
def add_country():
    name = request.form['country_name'].strip()
    if name and not Country.query.filter_by(name=name).first():
        db.session.add(Country(name=name))
        db.session.commit()
        flash('Country added!', 'success')
    return redirect(url_for('masters'))

@app.route('/masters/country/<int:country_id>/delete', methods=['POST'])
def delete_country(country_id):
    country = Country.query.get_or_404(country_id)
    db.session.delete(country)
    db.session.commit()
    flash('Country deleted!', 'success')
    return redirect(url_for('masters'))

@app.route('/masters/sector/add', methods=['POST'])
def add_sector():
    name = request.form['sector_name'].strip()
    if name and not Sector.query.filter_by(name=name).first():
        db.session.add(Sector(name=name))
        db.session.commit()
        flash('Sector added!', 'success')
    return redirect(url_for('masters'))

@app.route('/masters/sector/<int:sector_id>/delete', methods=['POST'])
def delete_sector(sector_id):
    sector = Sector.query.get_or_404(sector_id)
    db.session.delete(sector)
    db.session.commit()
    flash('Sector deleted!', 'success')
    return redirect(url_for('masters'))

@app.route('/audit_log')
def audit_log():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(200).all()
    return render_template('audit_log.html', logs=logs)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
