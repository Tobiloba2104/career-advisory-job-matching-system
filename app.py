import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///career.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)  # 'jobseeker' or 'employer'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Job seeker specific
    skills = db.Column(db.String(500))
    education = db.Column(db.String(200))
    experience = db.Column(db.String(500))
    
    # Employer specific
    company_name = db.Column(db.String(100))
    industry = db.Column(db.String(100))

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    required_skills = db.Column(db.String(500), nullable=False)
    location = db.Column(db.String(100))
    salary = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    seeker_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected

# Routes
@app.route('/')
def home():
    jobs = Job.query.filter_by(is_active=True).order_by(Job.created_at.desc()).limit(5).all()
    return render_template('index.html', jobs=jobs)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fullname = request.form['fullname']
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']
        
        # Check if email exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered!', 'error')
            return redirect(url_for('register'))
        
        # Create new user
        new_user = User(
            fullname=fullname,
            email=email,
            password=generate_password_hash(password),
            user_type=user_type
        )
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash(f'Welcome back, {user.fullname}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password!', 'error')
    
    return render_template('login.html')

@app.route ('/update-skills', methods=['GET', 'POST'])
def update_skills():
    user_id = session.get('user_id')
    if not user_id:
        flash('Please login to update your skills!', 'error')
        return redirect(url_for('login'))
    
    user = User.query.get(user_id)
    
    if request.method == 'POST':
        skills = request.form['skills']
        education = request.form['education']
        experience = request.form['experience']
        
        user.skills = skills
        user.education = education
        user.experience = experience
        
        db.session.commit()
        
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('update_skills.html', user=user)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if not session.get('user_id'):
        flash('Please login to view your dashboard!', 'error')
        return redirect(url_for('login'))

    # Get all active jobs for job seekers
    jobs = Job.query.filter_by(is_active=True).all()
    job_employer_pairs= []
    for job in jobs:
        employer = User.query.get(job.employer_id)
        company_name = employer.fullname if employer else "Unknown Employer"
        job_employer_pairs.append((job, company_name))
    return render_template('dashboard.html', jobs=job_employer_pairs)

@app.route('/post-job', methods=['GET', 'POST'])
def post_job():
    user_id = session.get('user_id')
    if not user_id:
        flash('Please login to post a job!', 'error')
        return redirect(url_for('login'))
    
    user = User.query.get(user_id)
    if not user or user.user_type != 'employer':
        flash('Only employers can post jobs!', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        required_skills = request.form['required_skills']
        location = request.form['location']
        salary = request.form['salary']
        
        new_job = Job(
            employer_id=user_id,
            title=title,
            description=description,
            required_skills=required_skills,
            location=location,
            salary=salary
        )
        db.session.add(new_job)
        db.session.commit()
        
        flash('Job posted successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('post_job.html')

@app.route('/match-jobs')
def match_jobs():
    user_id = session.get('user_id')
    if not user_id:
        flash('Please login to find matching jobs!', 'error')
        return redirect(url_for('login'))

    current_user = User.query.get(user_id)
    user_skill_list = [s.strip().lower() for s in (current_user.skills or "").split(',') if s.strip()]

    if not user_skill_list:
        flash('Add your skills first so we can match you with jobs!', 'error')
        return redirect(url_for('update_skills'))

    all_jobs = Job.query.filter_by(is_active=True).all()
    matched_jobs = []

    for job in all_jobs:
        job_skills = [s.strip().lower() for s in job.required_skills.split(',') if s.strip()]

        # Calculate match score
        match_count = sum(1 for skill in user_skill_list if skill in job_skills)
        if match_count > 0:
            matched_jobs.append((job, match_count))

    # Sort by match score
    matched_jobs.sort(key=lambda x: x[1], reverse=True)

    return render_template('matches.html', matches=matched_jobs)

@app.route('/career-advice')
def career_advice():
    user_id = session.get('user_id')
    if not user_id:
        flash('Please login to view career advice!', 'error')
        return redirect(url_for('login'))

    current_user = User.query.get(user_id)
    user_skill_list = [s.strip().lower() for s in (current_user.skills or "").split(',') if s.strip()]

    # Count how often each skill appears across all active job postings
    all_jobs = Job.query.filter_by(is_active=True).all()
    skill_demand = {}
    for job in all_jobs:
        job_skills = [s.strip().lower() for s in job.required_skills.split(',') if s.strip()]
        for skill in job_skills:
            skill_demand[skill] = skill_demand.get(skill, 0) + 1

    # Sort skills by how in-demand they are, most requested first
    sorted_skills = sorted(skill_demand.items(), key=lambda x: x[1], reverse=True)

    # Find in-demand skills the user does not already have
    missing_skills = [(skill, count) for skill, count in sorted_skills if skill not in user_skill_list]

    return render_template('career_advice.html',
                           missing_skills=missing_skills[:5],
                           user_skills=current_user.skills)

@app.route('/apply/<int:job_id>', methods=['GET', 'POST'])
def apply_job(job_id):
    user_id = session.get('user_id')
    if not user_id:
        flash('Please login to apply for jobs!', 'error')
        return redirect(url_for('login'))

    job = Job.query.get_or_404(job_id)
    user = User.query.get(user_id)

    if not user or user.user_type != 'jobseeker':
        flash('Only job seekers can apply for jobs!', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        already_applied = Application.query.filter_by(job_id=job_id, seeker_id=user_id).first()
        if already_applied:
            flash('You have already applied for this job!', 'error')
            return redirect(url_for('dashboard'))

        new_application = Application(
            job_id=job_id,
            seeker_id=user_id,
            status='pending'
        )
        db.session.add(new_application)
        db.session.commit()

        flash('Application submitted successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('apply_job.html', job=job)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
