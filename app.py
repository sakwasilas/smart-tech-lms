from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)

import os
import json
import PyPDF2
import math
import re
from math import ceil

from werkzeug.utils import secure_filename

from datetime import datetime
from sqlalchemy import or_, func, text

from connections import db_session
from models import (
    User,
    Student,
    Course,
    Module,
    Enrollment,
    Payment,
    StudentModuleProgress,
    Teacher,
    Assignment,
    AssignmentSubmission,
    CourseTeacher,
    Announcement,
    Quiz,
    QuizQuestion,
    QuizAttempt,
    Question,
    Answer,
    Notification
)

app = Flask(__name__)
app.secret_key = "silassakwarechoivanadasa"

# ==================================================
# FILE UPLOAD CONFIGURATION
# ==================================================

# Folder where uploaded files will be stored
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")

# Maximum upload size (500 MB)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

# Create uploads folder if it doesn't exist
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Allowed file types for video
ALLOWED_EXTENSIONS = {
    "pdf",
    "mp4",
    "avi",
    "mov",
    "mkv"
}

def allowed_file(filename):
    return (
        "." in filename and
        filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


# ==========================================
# HOME
# ==========================================

@app.route("/")
def home():
    return redirect(url_for("login"))


# ==================================================
# LOGIN
# ==================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email").strip()
        password = request.form.get("password")

        user = db_session.query(User).filter_by(
            email=email
        ).first()

        # Invalid login
        if not user or user.password != password:
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

        # Create session
        session["user_id"] = user.id
        session["email"] = user.email
        session["role"] = user.role

        # ADMIN
        if user.role == "admin":
            return redirect(url_for("admin_dashboard"))

        # TEACHER
        elif user.role == "teacher":
            return redirect(url_for("teacher_dashboard"))

        # STUDENT
        elif user.role == "student":
            return redirect(url_for("student_dashboard"))

        # Unknown role
        session.clear()
        flash("Invalid user role.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ==================================================
# STUDENT REGISTER
# ==================================================

@app.route("/student_register", methods=["GET", "POST"])
def student_register():
    if request.method == "POST":
        fullname = request.form.get("fullname")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # Check passwords
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("student_register"))

        # Check existing email
        existing_user = db_session.query(User).filter_by(
            email=email
        ).first()

        if existing_user:
            flash("Email already exists.", "warning")
            return redirect(url_for("student_register"))

        # Create User Account
        user = User(
            fullname=fullname,
            email=email,
            phone=phone,
            password=password,
            role="student",
            status="Active"
        )

        db_session.add(user)
        db_session.commit()

        # Create Student Profile
        student = Student(
            user_id=user.id,
            fullname=fullname,
            email=email,
            phone=phone
        )

        db_session.add(student)
        db_session.commit()

        flash("Registration successful. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("students/register.html")


# ==================================================
# ==================================================
# STUDENT SECTION
# ==================================================
# ==================================================

# ==================================================
# STUDENT DASHBOARD
# ==================================================

@app.route("/student/dashboard")
def student_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    student = db_session.query(Student).filter_by(
        user_id=session["user_id"]
    ).first()

    if not student:
        flash("Student profile not found.", "danger")
        return redirect(url_for("login"))

    # Courses already enrolled
    enrolled_course_ids = [
        enrollment.course_id
        for enrollment in student.enrollments
    ]

    # Available courses
    courses = db_session.query(Course).filter(
        Course.status == "Active",
        ~Course.id.in_(enrolled_course_ids)
    ).all()

    # My enrolled courses with course details
    my_courses = db_session.query(Enrollment).filter_by(
        student_id=student.id
    ).all()
    
    # Explicitly load the course for each enrollment
    for enrollment in my_courses:
        enrollment.course = db_session.query(Course).filter_by(
            id=enrollment.course_id
        ).first()

    # Get notifications
    notifications = db_session.query(Notification).filter_by(
        user_id=session["user_id"],
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(10).all()

    return render_template(
        "students/student_dashboard.html",
        student=student,
        courses=courses,
        my_courses=my_courses,
        notifications=notifications
    )


# ==================================================
# ENROLL COURSE - Updated for Free/Paid courses
# ==================================================

@app.route("/enroll/<int:course_id>", methods=["POST"])
def enroll(course_id):
    if "user_id" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    # Logged in student
    student = db_session.query(Student).filter_by(
        user_id=session["user_id"]
    ).first()

    if not student:
        flash("Student profile not found.", "danger")
        return redirect(url_for("student_dashboard"))

    # Selected course
    course = db_session.query(Course).filter_by(
        id=course_id
    ).first()

    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("student_dashboard"))

    # Check existing enrollment
    existing = db_session.query(Enrollment).filter_by(
        student_id=student.id,
        course_id=course.id
    ).first()

    if existing:
        flash("You are already enrolled in this course.", "warning")
        return redirect(url_for("student_dashboard"))

    # Determine payment status based on course type
    if course.is_free:
        # FREE COURSE - Auto-approved
        payment_status = "Paid"
        
        # Create enrollment
        enrollment = Enrollment(
            student_id=student.id,
            course_id=course.id,
            date_enrolled=datetime.now(),
            payment_status=payment_status,
            status="Active"
        )
        db_session.add(enrollment)
        db_session.flush()  # Get enrollment.id
        
        # Create a dummy payment record for free courses
        payment = Payment(
            enrollment_id=enrollment.id,
            amount=0,
            phone="FREE_ENROLLMENT",
            transaction_code=f"FREE_{course.id}_{student.id}_{int(datetime.now().timestamp())}",
            status="Verified",
            date_paid=datetime.now()
        )
        db_session.add(payment)
        db_session.commit()
        
        flash("Successfully enrolled in free course!", "success")
        # Redirect directly to course for free courses
        return redirect(url_for("access_course", course_id=course.id))
    
    else:
        # PAID COURSE - Requires payment verification
        enrollment = Enrollment(
            student_id=student.id,
            course_id=course.id,
            date_enrolled=datetime.now(),
            payment_status="Pending",
            status="Active"
        )
        db_session.add(enrollment)
        db_session.commit()
        
        flash("Successfully enrolled in course. Please complete payment.", "success")
        return redirect(url_for("student_dashboard"))


# ==================================================
# PAYMENT PAGE
# ==================================================

@app.route("/payment/<int:enrollment_id>")
def payment_page(enrollment_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    enrollment = db_session.query(
        Enrollment
    ).filter_by(
        id=enrollment_id
    ).first()

    if not enrollment:
        flash("Enrollment not found.", "danger")
        return redirect(url_for("student_dashboard"))
    
    # Load course for the enrollment
    enrollment.course = db_session.query(Course).filter_by(
        id=enrollment.course_id
    ).first()

    return render_template(
        "students/payment.html",
        enrollment=enrollment
    )


# ==================================================
# SUBMIT PAYMENT - Payment requires admin verification
# ==================================================

@app.route("/submit_payment/<int:enrollment_id>", methods=["POST"])
def submit_payment(enrollment_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    enrollment = db_session.query(
        Enrollment
    ).filter_by(
        id=enrollment_id
    ).first()

    if not enrollment:
        flash("Enrollment not found.", "danger")
        return redirect(url_for("student_dashboard"))

    if enrollment.payment_status == "Paid":
        flash("This course has already been paid for.", "warning")
        return redirect(url_for("student_dashboard"))

    phone = request.form.get("phone")
    transaction_code = request.form.get("transaction_code")

    existing_payment = db_session.query(
        Payment
    ).filter_by(
        transaction_code=transaction_code
    ).first()

    if existing_payment:
        flash("This transaction code has already been used.", "warning")
        return redirect(
            url_for(
                "payment_page",
                enrollment_id=enrollment_id
            )
        )

    # Create payment with Pending status (requires admin verification)
    payment = Payment(
        enrollment_id=enrollment.id,
        amount=enrollment.course.fee,
        phone=phone,
        transaction_code=transaction_code,
        status="Pending",
        date_paid=datetime.now()
    )

    db_session.add(payment)
    db_session.commit()

    flash("Payment submitted successfully! Please wait for admin verification.", "success")
    return redirect(url_for("student_dashboard"))


# ==================================================
# ACCESS COURSE - FIXED for "Paid" and "Verified" status
# ==================================================

@app.route("/course/<int:course_id>")
def access_course(course_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    student = db_session.query(Student).filter_by(
        user_id=session["user_id"]
    ).first()

    if not student:
        flash("Student profile not found.", "danger")
        return redirect(url_for("student_dashboard"))

    enrollment = db_session.query(Enrollment).filter_by(
        student_id=student.id,
        course_id=course_id
    ).first()

    if not enrollment:
        flash("You are not enrolled in this course.", "warning")
        return redirect(url_for("student_dashboard"))

    course = db_session.query(Course).filter_by(
        id=course_id
    ).first()

    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("student_dashboard"))

    # Check payment only for paid courses
    if not course.is_free:
        if enrollment.payment_status not in ["Paid", "Verified"]:
            # Check if there's a pending payment
            pending_payment = db_session.query(Payment).filter_by(
                enrollment_id=enrollment.id,
                status="Pending"
            ).first()
            
            if pending_payment:
                flash("Your payment is pending verification. Please wait for admin approval.", "warning")
            else:
                flash("Please complete payment first.", "warning")
            return redirect(url_for("student_dashboard"))

    modules = db_session.query(Module).filter_by(
        course_id=course_id
    ).order_by(
        Module.module_number
    ).all()

    assignments = db_session.query(Assignment).filter_by(
        course_id=course_id,
        status="Active"
    ).all()

    quizzes = db_session.query(Quiz).filter_by(
        course_id=course_id,
        status="Active"
    ).all()

    announcements = db_session.query(Announcement).filter_by(
        course_id=course_id
    ).order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc()).all()

    # Check if student has submitted each assignment
    for assignment in assignments:
        submission = db_session.query(AssignmentSubmission).filter_by(
            assignment_id=assignment.id,
            student_id=student.id
        ).first()
        assignment.submitted = submission is not None
        assignment.submission = submission

    # Check if student has taken each quiz
    for quiz in quizzes:
        attempt = db_session.query(QuizAttempt).filter_by(
            quiz_id=quiz.id,
            student_id=student.id
        ).first()
        quiz.attempted = attempt is not None
        quiz.attempt = attempt

    completed_records = db_session.query(
        StudentModuleProgress
    ).filter_by(
        student_id=student.id,
        status="Completed"
    ).all()

    completed_ids = [
        record.module_id
        for record in completed_records
    ]

    for index, module in enumerate(modules):
        if module.id in completed_ids:
            module.completed = True
            module.locked = False
        elif index == 0:
            module.completed = False
            module.locked = False
        else:
            previous_module = modules[index - 1]
            if previous_module.id in completed_ids:
                module.locked = False
            else:
                module.locked = True
            module.completed = False

    return render_template(
        "students/course.html",
        course=course,
        modules=modules,
        assignments=assignments,
        quizzes=quizzes,
        announcements=announcements,
        is_free=course.is_free
    )


# ==================================================
# ADMIN - VERIFY PAYMENTS
# ==================================================

@app.route("/admin/verify_payments")
def admin_verify_payments():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))
    
    # Get all pending payments
    pending_payments = db_session.query(Payment).filter_by(
        status="Pending"
    ).all()
    
    # Get all verified payments
    verified_payments = db_session.query(Payment).filter_by(
        status="Verified"
    ).order_by(Payment.id.desc()).limit(20).all()
    
    return render_template(
        "admin/verify_payments.html",
        pending_payments=pending_payments,
        verified_payments=verified_payments
    )


@app.route("/admin/verify_payment/<int:payment_id>")
def admin_verify_payment(payment_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))
    
    payment = db_session.query(Payment).filter_by(id=payment_id).first()
    if not payment:
        flash("Payment not found.", "danger")
        return redirect(url_for("admin_verify_payments"))
    
    # Verify payment
    payment.status = "Verified"
    payment.verified_at = datetime.now()
    
    # Update enrollment payment status to "Paid"
    enrollment = db_session.query(Enrollment).filter_by(id=payment.enrollment_id).first()
    if enrollment:
        enrollment.payment_status = "Paid"
    
    db_session.commit()
    
    flash(f"Payment {payment.transaction_code} verified successfully!", "success")
    return redirect(url_for("admin_verify_payments"))


@app.route("/admin/reject_payment/<int:payment_id>")
def admin_reject_payment(payment_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))
    
    payment = db_session.query(Payment).filter_by(id=payment_id).first()
    if not payment:
        flash("Payment not found.", "danger")
        return redirect(url_for("admin_verify_payments"))
    
    # Reject payment
    payment.status = "Rejected"
    
    db_session.commit()
    
    flash(f"Payment {payment.transaction_code} rejected.", "warning")
    return redirect(url_for("admin_verify_payments"))


# ==================================================
# MODULE CONTENT
# ==================================================

@app.route("/module_content/<int:module_id>")
def module_content(module_id):
    """Get module content with pagination for LMS display"""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    student = db_session.query(Student).filter_by(
        user_id=session["user_id"]
    ).first()
    
    if not student:
        flash("Student profile not found.", "danger")
        return redirect(url_for("student_dashboard"))
    
    module = db_session.query(Module).filter_by(
        id=module_id
    ).first()
    
    if not module:
        flash("Module not found.", "danger")
        return redirect(url_for("student_dashboard"))
    
    # Check if module is completed
    completed = db_session.query(
        StudentModuleProgress
    ).filter_by(
        student_id=student.id,
        module_id=module.id,
        status="Completed"
    ).first() is not None
    
    # Get page number from query string
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
    
    content_pages = []
    total_pages = 0
    
    # ===== PRIORITY 1: Use content field (rich text from editor) =====
    if module.content and module.content.strip():
        content = module.content
        
        # Try to split by --- or *** or the old divider
        if '---' in content or '***' in content or '--------------------------------------------------' in content:
            # Split by multiple dividers
            sections = re.split(r'---|\*\*\*|--------------------------------------------------', content)
            for section in sections:
                section = section.strip()
                if section:
                    content_pages.append(section)
        else:
            # If no dividers, split by headings (## or ###)
            headings = re.split(r'(?=##\s|\n##\s|\n###\s)', content)
            for heading in headings:
                heading = heading.strip()
                if heading:
                    content_pages.append(heading)
            
            # If still too long or no headings, split by paragraphs
            if len(content_pages) <= 1:
                paragraphs = content.split('\n\n')
                current_chunk = ""
                for para in paragraphs:
                    if len(current_chunk) + len(para) < 1500:
                        current_chunk += para + "\n\n"
                    else:
                        if current_chunk:
                            content_pages.append(current_chunk.strip())
                        current_chunk = para + "\n\n"
                if current_chunk:
                    content_pages.append(current_chunk.strip())
    
    # ===== FALLBACK 1: If no content, try PDF =====
    elif module.pdf_file:
        pdf_path = os.path.join(app.root_path, 'static', 'uploads', 'pdfs', module.pdf_file)
        
        if not os.path.exists(pdf_path):
            content_pages = ["PDF file not found. Please contact your instructor."]
        else:
            try:
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    total_pages = len(pdf_reader.pages)
                    
                    all_text = ""
                    for page_num in range(total_pages):
                        page_obj = pdf_reader.pages[page_num]
                        text = page_obj.extract_text()
                        if text:
                            all_text += text + "\n\n"
                    
                    chunk_size = 2000
                    if all_text:
                        paragraphs = all_text.split('\n\n')
                        current_chunk = ""
                        for para in paragraphs:
                            if len(current_chunk) + len(para) < chunk_size:
                                current_chunk += para + "\n\n"
                            else:
                                if current_chunk:
                                    content_pages.append(current_chunk.strip())
                                current_chunk = para + "\n\n"
                        if current_chunk:
                            content_pages.append(current_chunk.strip())
                    
                    if not content_pages:
                        content_pages = ["No text content could be extracted from this PDF."]
                        
            except Exception as e:
                content_pages = [f"Error reading PDF: {str(e)}"]
    
    # ===== FALLBACK 2: Use description =====
    elif module.description:
        # Split description into chunks
        desc_parts = module.description.split('\n\n')
        current_chunk = ""
        for part in desc_parts:
            if len(current_chunk) + len(part) < 1000:
                current_chunk += part + "\n\n"
            else:
                if current_chunk:
                    content_pages.append(current_chunk.strip())
                current_chunk = part + "\n\n"
        if current_chunk:
            content_pages.append(current_chunk.strip())
    
    # ===== FINAL FALLBACK =====
    else:
        content_pages = ["No content available for this module."]
    
    total_content_pages = len(content_pages)
    
    if page > total_content_pages:
        page = total_content_pages
    
    current_content = content_pages[page - 1] if content_pages else "No content available."
    
    has_previous = page > 1
    has_next = page < total_content_pages
    
    modules = db_session.query(Module).filter_by(
        course_id=module.course_id
    ).order_by(
        Module.module_number
    ).all()
    
    current_index = next(
        (
            index
            for index, item in enumerate(modules)
            if item.id == module.id
        ),
        0
    )
    
    previous_module = modules[current_index - 1] if current_index > 0 else None
    next_module = modules[current_index + 1] if current_index < len(modules) - 1 else None
    
    return render_template(
        "students/module_content.html",
        module=module,
        current_content=current_content,
        current_page=page,
        total_pages=total_content_pages,
        has_previous=has_previous,
        has_next=has_next,
        previous_module=previous_module,
        next_module=next_module,
        completed=completed,
        course=module.course
    )


# ==================================================
# LEARN MODULE - Redirect to module_content
# ==================================================

@app.route("/learn/<int:module_id>")
def learn_module(module_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    return redirect(url_for('module_content', module_id=module_id))


# ==================================================
# COMPLETE MODULE
# ==================================================

@app.route("/complete_module/<int:module_id>")
def complete_module(module_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    student = db_session.query(Student).filter_by(
        user_id=session["user_id"]
    ).first()
    
    if not student:
        flash("Student profile not found.", "danger")
        return redirect(url_for("student_dashboard"))
    
    existing = db_session.query(
        StudentModuleProgress
    ).filter_by(
        student_id=student.id,
        module_id=module_id
    ).first()
    
    if not existing:
        progress = StudentModuleProgress(
            student_id=student.id,
            module_id=module_id,
            status="Completed",
            completed_date=datetime.now()
        )
        db_session.add(progress)
        db_session.commit()
        flash("Module completed successfully!", "success")
    else:
        flash("Module already completed.", "info")
    
    return redirect(url_for('access_course', course_id=module.course_id))


# ==================================================
# STUDENT SUBMIT ASSIGNMENT
# ==================================================

@app.route("/student/submit_assignment/<int:assignment_id>", methods=["GET", "POST"])
def student_submit_assignment(assignment_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    student = db_session.query(Student).filter_by(
        user_id=session["user_id"]
    ).first()
    
    if not student:
        flash("Student profile not found.", "danger")
        return redirect(url_for("student_dashboard"))
    
    assignment = db_session.query(Assignment).filter_by(
        id=assignment_id
    ).first()
    
    if not assignment:
        flash("Assignment not found.", "danger")
        return redirect(url_for("student_dashboard"))
    
    existing = db_session.query(AssignmentSubmission).filter_by(
        assignment_id=assignment_id,
        student_id=student.id
    ).first()
    
    if existing:
        flash("You have already submitted this assignment.", "warning")
        return redirect(url_for("access_course", course_id=assignment.course_id))
    
    if request.method == "POST":
        submission_text = request.form.get("submission_text")
        uploaded_file = request.files.get("file")
        
        file_name = None
        file_path = None
        
        if uploaded_file and uploaded_file.filename:
            filename = secure_filename(uploaded_file.filename)
            submission_folder = os.path.join(app.config["UPLOAD_FOLDER"], "submissions")
            os.makedirs(submission_folder, exist_ok=True)
            
            unique_filename = f"{student.id}_{assignment_id}_{filename}"
            file_path = os.path.join(submission_folder, unique_filename)
            uploaded_file.save(file_path)
            file_name = filename
        
        submission = AssignmentSubmission(
            assignment_id=assignment_id,
            student_id=student.id,
            file_name=file_name,
            file_path=file_path,
            submission_text=submission_text,
            status="Submitted"
        )
        
        db_session.add(submission)
        db_session.commit()
        
        flash("Assignment submitted successfully!", "success")
        return redirect(url_for("access_course", course_id=assignment.course_id))
    
    return render_template(
        "students/submit_assignment.html",
        assignment=assignment,
        student=student
    )


# ==================================================
# STUDENT - TAKE QUIZ
# ==================================================

@app.route("/student/take_quiz/<int:quiz_id>", methods=["GET", "POST"])
def student_take_quiz(quiz_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    student = db_session.query(Student).filter_by(
        user_id=session["user_id"]
    ).first()
    
    if not student:
        flash("Student profile not found.", "danger")
        return redirect(url_for("student_dashboard"))
    
    quiz = db_session.query(Quiz).filter_by(id=quiz_id).first()
    if not quiz:
        flash("Quiz not found.", "danger")
        return redirect(url_for("student_dashboard"))
    
    # Check if already attempted
    existing_attempt = db_session.query(QuizAttempt).filter_by(
        quiz_id=quiz_id,
        student_id=student.id
    ).first()
    
    if existing_attempt:
        flash("You have already taken this quiz.", "info")
        return redirect(url_for("access_course", course_id=quiz.course_id))
    
    questions = db_session.query(QuizQuestion).filter_by(quiz_id=quiz_id).all()
    
    if request.method == "POST":
        score = 0
        total_points = 0
        answers = {}
        
        for q in questions:
            total_points += q.points
            user_answer = request.form.get(f"question_{q.id}")
            answers[str(q.id)] = user_answer
            if user_answer == q.correct_answer:
                score += q.points
        
        # Calculate percentage
        percentage = (score / total_points * 100) if total_points > 0 else 0
        passed = percentage >= quiz.passing_score
        
        attempt = QuizAttempt(
            quiz_id=quiz_id,
            student_id=student.id,
            score=percentage,
            passed=passed,
            answers=json.dumps(answers),
            completed_at=datetime.now()
        )
        
        db_session.add(attempt)
        db_session.commit()
        
        flash(f"Quiz completed! You scored {percentage:.1f}%", "success" if passed else "warning")
        return redirect(url_for("access_course", course_id=quiz.course_id))
    
    return render_template(
        "students/take_quiz.html",
        quiz=quiz,
        questions=questions
    )


# ==================================================
# STUDENT - ASK QUESTION
# ==================================================

@app.route("/student/ask_question/<int:course_id>", methods=["GET", "POST"])
def student_ask_question(course_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    student = db_session.query(Student).filter_by(
        user_id=session["user_id"]
    ).first()
    
    if not student:
        flash("Student profile not found.", "danger")
        return redirect(url_for("student_dashboard"))
    
    course = db_session.query(Course).filter_by(id=course_id).first()
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("student_dashboard"))
    
    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        is_public = request.form.get("is_public") == "on"
        
        question = Question(
            course_id=course_id,
            student_id=student.id,
            user_id=session["user_id"],
            title=title,
            content=content,
            is_public=is_public
        )
        
        db_session.add(question)
        db_session.commit()
        
        flash("Question posted successfully!", "success")
        return redirect(url_for("access_course", course_id=course_id))
    
    return render_template(
        "students/ask_question.html",
        course=course,
        student=student
    )


# ==================================================
# STUDENT - VIEW QUESTIONS
# ==================================================

@app.route("/student/questions/<int:course_id>")
def student_questions(course_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    course = db_session.query(Course).filter_by(id=course_id).first()
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("student_dashboard"))
    
    questions = db_session.query(Question).filter_by(
        course_id=course_id
    ).order_by(Question.created_at.desc()).all()
    
    return render_template(
        "students/questions.html",
        course=course,
        questions=questions
    )


# ==================================================
# ==================================================
# ADMIN SECTION
# ==================================================
# ==================================================

# ==================================================
# ADMIN DASHBOARD - WITH PAGINATION
# ==================================================

@app.route("/admin_dashboard")
def admin_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    total_users = db_session.query(User).count()
    total_students = db_session.query(Student).count()
    total_teachers = db_session.query(Teacher).count()
    total_courses = db_session.query(Course).count()
    total_modules = db_session.query(Module).count()
    pending_students = db_session.query(Student).filter_by(
        status="Pending"
    ).count()
    
    # Count free vs paid courses
    free_courses = db_session.query(Course).filter_by(is_free=True).count()
    paid_courses = db_session.query(Course).filter_by(is_free=False).count()

    # Payment Statistics
    total_payments_count = db_session.query(Payment).count()
    total_revenue = db_session.query(func.sum(Payment.amount)).filter(
        Payment.status == "Verified"
    ).scalar() or 0
    paid_payments = db_session.query(Payment).filter_by(
        status="Verified"
    ).count()
    pending_payments = db_session.query(Payment).filter_by(
        status="Pending"
    ).count()

    # ===== PAGINATION FOR RECENT PAYMENTS =====
    # Get page number from query string (default: 1)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # Validate per_page
    if per_page not in [5, 10, 25, 50]:
        per_page = 10
    
    # Calculate total pages
    total_pages = ceil(total_payments_count / per_page) if total_payments_count > 0 else 1
    
    # Ensure page is within valid range
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Get paginated payments
    recent_payments = db_session.query(Payment).order_by(
        Payment.id.desc()
    ).limit(per_page).offset(offset).all()

    return render_template(
        "admin/admin_dashboard.html",
        total_users=total_users,
        total_students=total_students,
        total_teachers=total_teachers,
        total_courses=total_courses,
        total_modules=total_modules,
        pending_students=pending_students,
        total_payments=total_payments_count,
        total_revenue=total_revenue,
        paid_payments=paid_payments,
        pending_payments=pending_payments,
        recent_payments=recent_payments,
        page=page,
        total_pages=total_pages,
        total_payments_count=total_payments_count,
        per_page=per_page,
        free_courses=free_courses,
        paid_courses=paid_courses
    )


# ==================================================
# ADMIN - SELECT COURSE FOR ANNOUNCEMENTS
# ==================================================

@app.route("/admin/announcements")
def admin_announcements_list():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))
    
    courses = db_session.query(Course).filter_by(status="Active").all()
    
    return render_template("admin/announcements_list.html", courses=courses)


# ==================================================
# MANAGE STUDENTS (ADMIN)
# ==================================================

@app.route("/admin/students")
def manage_students():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    search = request.args.get("search", "").strip()
    status = request.args.get("status", "")

    students_query = db_session.query(Student)

    if search:
        students_query = students_query.filter(
            or_(
                Student.fullname.ilike(f"%{search}%"),
                Student.email.ilike(f"%{search}%"),
                Student.phone.ilike(f"%{search}%")
            )
        )

    if status:
        students_query = students_query.filter(
            Student.status == status
        )

    students = students_query.order_by(
        Student.id.desc()
    ).all()

    return render_template(
        "admin/students.html",
        students=students,
        search=search,
        status=status
    )


@app.route("/approve_student/<int:id>")
def approve_student(id):
    student = db_session.query(Student).filter_by(id=id).first()
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("manage_students"))
    
    student.status = "Approved"
    db_session.commit()
    flash("Student approved successfully.", "success")
    return redirect(url_for("manage_students"))


@app.route("/reject_student/<int:id>")
def reject_student(id):
    student = db_session.query(Student).filter_by(id=id).first()
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("manage_students"))
    
    student.status = "Rejected"
    db_session.commit()
    flash("Student rejected.", "warning")
    return redirect(url_for("manage_students"))


@app.route("/toggle_student/<int:id>")
def toggle_student(id):
    student = db_session.query(Student).filter_by(id=id).first()
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("manage_students"))
    
    if student.status == "Blocked":
        student.status = "Approved"
        flash("Student unblocked successfully.", "success")
    else:
        student.status = "Blocked"
        flash("Student blocked successfully.", "warning")

    db_session.commit()
    return redirect(url_for("manage_students"))


@app.route("/edit_student/<int:id>", methods=["GET", "POST"])
def edit_student(id):
    student = db_session.query(Student).filter_by(id=id).first()
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("manage_students"))

    if request.method == "POST":
        student.fullname = request.form.get("fullname")
        student.email = request.form.get("email")
        student.phone = request.form.get("phone")
        db_session.commit()
        flash("Student updated successfully.", "success")
        return redirect(url_for("manage_students"))

    return render_template("admin/edit_student.html", student=student)


@app.route("/delete_student/<int:id>")
def delete_student(id):
    student = db_session.query(Student).filter_by(id=id).first()
    if student:
        db_session.delete(student)
        db_session.commit()
        flash("Student deleted successfully.", "success")
    return redirect(url_for("manage_students"))


@app.route("/admin/mass_block_students", methods=["POST"])
def mass_block_students():
    ids = request.form.getlist("student_ids")
    if not ids:
        flash("No students selected.", "warning")
        return redirect(url_for("manage_students"))

    students = db_session.query(Student).filter(Student.id.in_(ids)).all()
    for student in students:
        student.status = "Blocked"
    db_session.commit()
    flash("Selected students blocked successfully.", "success")
    return redirect(url_for("manage_students"))


@app.route("/admin/mass_unblock_students", methods=["POST"])
def mass_unblock_students():
    ids = request.form.getlist("student_ids")
    if not ids:
        flash("No students selected.", "warning")
        return redirect(url_for("manage_students"))

    students = db_session.query(Student).filter(Student.id.in_(ids)).all()
    for student in students:
        student.status = "Approved"
    db_session.commit()
    flash("Selected students unblocked successfully.", "success")
    return redirect(url_for("manage_students"))


# ==================================================
# COURSE MANAGEMENT (ADMIN) - FIXED
# ==================================================

@app.route("/courses")
def courses():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    search = request.args.get("search", "").strip()
    query = db_session.query(Course)

    if search:
        query = query.filter(Course.course_name.like(f"%{search}%"))

    # Get all courses with their teacher assignments loaded
    courses = query.order_by(Course.id).all()
    
    # Load course_teachers relationship for each course
    for course in courses:
        # This ensures the relationship is loaded
        _ = course.course_teachers

    # Get all active teachers for the modal dropdown
    all_teachers = db_session.query(Teacher).filter_by(status="Active").all()

    return render_template(
        "admin/courses.html",
        courses=courses,
        search=search,
        all_teachers=all_teachers
    )


@app.route("/add_course", methods=["GET", "POST"])
def add_course():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        course_name = request.form.get("course_name")
        course_code = request.form.get("course_code")
        duration = request.form.get("duration")
        fee = request.form.get("fee", 0)
        description = request.form.get("description")
        career_objectives = request.form.get("career_objectives")
        prerequisites = request.form.get("prerequisites")
        meeting_link = request.form.get("meeting_link")
        status = request.form.get("status")
        
        # Handle the is_free checkbox
        is_free = request.form.get("is_free") == "on"
        
        # If course is free, set fee to 0
        if is_free:
            fee = 0

        existing = db_session.query(Course).filter_by(course_name=course_name).first()
        if existing:
            flash("Course already exists.", "warning")
            return redirect(url_for("courses"))

        course = Course(
            course_name=course_name,
            course_code=course_code,
            duration=duration,
            fee=fee,
            description=description,
            career_objectives=career_objectives,
            prerequisites=prerequisites,
            meeting_link=meeting_link,
            status=status,
            is_free=is_free
        )

        db_session.add(course)
        db_session.commit()
        flash("Course added successfully.", "success")
        return redirect(url_for("courses"))

    return render_template("admin/add_course.html")


@app.route("/edit_course/<int:id>", methods=["GET", "POST"])
def edit_course(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    course = db_session.query(Course).get(id)
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("courses"))

    if request.method == "POST":
        course.course_name = request.form.get("course_name")
        course.course_code = request.form.get("course_code")
        course.duration = request.form.get("duration")
        course.fee = request.form.get("fee", 0)
        course.description = request.form.get("description")
        course.career_objectives = request.form.get("career_objectives")
        course.prerequisites = request.form.get("prerequisites")
        course.meeting_link = request.form.get("meeting_link")
        course.status = request.form.get("status")
        
        # Handle the is_free checkbox
        course.is_free = request.form.get("is_free") == "on"
        
        # If course is free, set fee to 0
        if course.is_free:
            course.fee = 0
        
        db_session.commit()
        flash("Course updated successfully.", "success")
        return redirect(url_for("courses"))

    return render_template("admin/edit_course.html", course=course)


@app.route("/delete_course/<int:id>")
def delete_course(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    course = db_session.query(Course).get(id)
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("courses"))

    db_session.delete(course)
    db_session.commit()
    flash("Course deleted successfully.", "success")
    return redirect(url_for("courses"))


@app.route("/activate_course/<int:id>")
def activate_course(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    course = db_session.query(Course).get(id)
    if course:
        course.status = "Active"
        db_session.commit()
        flash("Course activated successfully.", "success")
    return redirect(url_for("courses"))


@app.route("/deactivate_course/<int:id>")
def deactivate_course(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    course = db_session.query(Course).get(id)
    if course:
        course.status = "Inactive"
        db_session.commit()
        flash("Course deactivated successfully.", "success")
    return redirect(url_for("courses"))


# ==================================================
# ADMIN - ASSIGN TEACHER TO COURSE - FIXED
# ==================================================

@app.route("/admin/assign_teacher/<int:course_id>", methods=["GET", "POST"])
def assign_teacher(course_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    course = db_session.query(Course).filter_by(id=course_id).first()
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("courses"))

    teachers = db_session.query(Teacher).filter_by(status="Active").all()
    
    assigned_teachers = db_session.query(CourseTeacher).filter_by(
        course_id=course_id,
        status="Active"
    ).all()
    assigned_ids = [ct.teacher_id for ct in assigned_teachers]

    if request.method == "POST":
        teacher_id = request.form.get("teacher_id")
        
        # Verify teacher exists
        teacher = db_session.query(Teacher).filter_by(id=teacher_id).first()
        if not teacher:
            flash("Teacher not found.", "danger")
            return redirect(url_for("assign_teacher", course_id=course_id))
        
        # Check if already assigned (active)
        existing = db_session.query(CourseTeacher).filter_by(
            course_id=course_id,
            teacher_id=teacher_id,
            status="Active"
        ).first()
        
        if existing:
            flash("Teacher already assigned to this course.", "warning")
            return redirect(url_for("assign_teacher", course_id=course_id))
        
        # Check if there's an inactive assignment (reactivate it)
        inactive = db_session.query(CourseTeacher).filter_by(
            course_id=course_id,
            teacher_id=teacher_id,
            status="Inactive"
        ).first()
        
        if inactive:
            # Reactivate instead of creating new
            inactive.status = "Active"
            inactive.assigned_date = datetime.now()
            db_session.commit()
            flash(f"{teacher.fullname} re-assigned to {course.course_name}!", "success")
            return redirect(url_for("assign_teacher", course_id=course_id))
        
        # Create new assignment
        assignment = CourseTeacher(
            course_id=course_id,
            teacher_id=teacher_id,
            status="Active"
        )
        db_session.add(assignment)
        db_session.commit()
        
        flash(f"{teacher.fullname} assigned to {course.course_name} successfully!", "success")
        
        # Redirect back to the course management page
        return redirect(url_for('courses'))

    return render_template(
        "admin/assign_teacher.html",
        course=course,
        teachers=teachers,
        assigned_teachers=assigned_teachers,
        assigned_ids=assigned_ids
    )


@app.route("/admin/remove_teacher/<int:assignment_id>")
def remove_teacher(assignment_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    assignment = db_session.query(CourseTeacher).filter_by(id=assignment_id).first()
    if not assignment:
        flash("Assignment not found.", "danger")
        return redirect(url_for("courses"))

    course_id = assignment.course_id
    db_session.delete(assignment)
    db_session.commit()
    
    flash("Teacher removed from course.", "success")
    return redirect(url_for("courses"))


# ==================================================
# ADMIN - MANAGE ANNOUNCEMENTS FOR A COURSE
# ==================================================

@app.route("/admin/announcements/<int:course_id>", methods=["GET", "POST"])
def admin_announcements(course_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    course = db_session.query(Course).filter_by(id=course_id).first()
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("courses"))

    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        is_pinned = request.form.get("is_pinned") == "on"
        
        announcement = Announcement(
            course_id=course_id,
            author_id=session["user_id"],
            title=title,
            content=content,
            is_pinned=is_pinned
        )
        db_session.add(announcement)
        db_session.commit()
        
        flash("Announcement created successfully!", "success")
        return redirect(url_for("admin_announcements", course_id=course_id))

    announcements = db_session.query(Announcement).filter_by(
        course_id=course_id
    ).order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc()).all()

    return render_template(
        "admin/announcements.html",
        course=course,
        announcements=announcements
    )


# ==================================================
# MODULE MANAGEMENT (ADMIN)
# ==================================================

@app.route("/modules", methods=["GET", "POST"])
def modules():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    search = request.args.get("search", "").strip()
    query = db_session.query(Module)

    if search:
        query = query.filter(Module.title.like(f"%{search}%"))

    modules = query.order_by(Module.course_id, Module.module_number).all()
    courses = db_session.query(Course).filter_by(status="Active").all()

    return render_template("admin/modules.html", modules=modules, courses=courses, search=search)


@app.route("/add_module", methods=["POST"])
def add_module():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    course_id = request.form.get("course_id")
    module_number = request.form.get("module_number")
    title = request.form.get("title")
    description = request.form.get("description")
    content = request.form.get("content")
    status = request.form.get("status", "Active")

    if not course_id or not module_number or not title:
        flash("Course, Module Number and Title are required.", "danger")
        return redirect(url_for("modules"))

    existing = db_session.query(Module).filter_by(
        course_id=course_id,
        module_number=module_number
    ).first()

    if existing:
        flash(f"Module {module_number} already exists for this course.", "warning")
        return redirect(url_for("modules"))

    pdf_file = None
    pdf_upload = request.files.get("pdf_file")
    if pdf_upload and pdf_upload.filename:
        if not pdf_upload.filename.lower().endswith(".pdf"):
            flash("PDF file must be in PDF format.", "danger")
            return redirect(url_for("modules"))
        
        filename = secure_filename(pdf_upload.filename)
        pdf_folder = os.path.join(app.config["UPLOAD_FOLDER"], "pdfs")
        os.makedirs(pdf_folder, exist_ok=True)
        pdf_upload.save(os.path.join(pdf_folder, filename))
        pdf_file = filename

    video_file = None
    video_upload = request.files.get("video_file")
    if video_upload and video_upload.filename:
        if not allowed_file(video_upload.filename):
            flash("Invalid video format.", "danger")
            return redirect(url_for("modules"))
        
        filename = secure_filename(video_upload.filename)
        video_folder = os.path.join(app.config["UPLOAD_FOLDER"], "videos")
        os.makedirs(video_folder, exist_ok=True)
        video_upload.save(os.path.join(video_folder, filename))
        video_file = filename

    meeting_link = request.form.get("meeting_link")

    module = Module(
        course_id=course_id,
        module_number=module_number,
        title=title,
        description=description,
        content=content,
        pdf_file=pdf_file,
        video_file=video_file,
        meeting_link=meeting_link,
        status=status
    )

    db_session.add(module)
    db_session.commit()
    flash("Module added successfully.", "success")
    return redirect(url_for("modules"))


@app.route("/edit_module/<int:id>", methods=["GET", "POST"])
def edit_module(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    module = db_session.query(Module).filter_by(id=id).first()
    if not module:
        flash("Module not found.", "danger")
        return redirect(url_for("modules"))

    if request.method == "POST":
        module.course_id = request.form.get("course_id")
        module.module_number = request.form.get("module_number")
        module.title = request.form.get("title")
        module.description = request.form.get("description")
        module.content = request.form.get("content")
        module.status = request.form.get("status")

        # Handle PDF upload
        pdf_upload = request.files.get("pdf_file")
        if pdf_upload and pdf_upload.filename:
            if not pdf_upload.filename.lower().endswith(".pdf"):
                flash("PDF file must be in PDF format.", "danger")
                return redirect(url_for("edit_module", id=module.id))
            
            filename = secure_filename(pdf_upload.filename)
            pdf_folder = os.path.join(app.config["UPLOAD_FOLDER"], "pdfs")
            os.makedirs(pdf_folder, exist_ok=True)
            pdf_upload.save(os.path.join(pdf_folder, filename))
            module.pdf_file = filename

        # Handle Video upload
        video_upload = request.files.get("video_file")
        if video_upload and video_upload.filename:
            if not allowed_file(video_upload.filename):
                flash("Invalid video format.", "danger")
                return redirect(url_for("edit_module", id=module.id))
            
            filename = secure_filename(video_upload.filename)
            video_folder = os.path.join(app.config["UPLOAD_FOLDER"], "videos")
            os.makedirs(video_folder, exist_ok=True)
            video_upload.save(os.path.join(video_folder, filename))
            module.video_file = filename

        # Handle Meeting Link
        meeting_link = request.form.get("meeting_link")
        if meeting_link:
            module.meeting_link = meeting_link

        db_session.commit()
        flash("Module updated successfully.", "success")
        return redirect(url_for("modules"))

    courses = db_session.query(Course).all()
    return render_template("admin/edit_module.html", module=module, courses=courses)


@app.route("/delete_module/<int:id>")
def delete_module(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    module = db_session.query(Module).filter_by(id=id).first()
    if not module:
        flash("Module not found.", "danger")
        return redirect(url_for("modules"))

    db_session.delete(module)
    db_session.commit()
    flash("Module deleted successfully.", "success")
    return redirect(url_for("modules"))


@app.route("/activate_module/<int:id>")
def activate_module(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    module = db_session.query(Module).filter_by(id=id).first()
    if module:
        module.status = "Active"
        db_session.commit()
        flash("Module activated successfully.", "success")
    return redirect(url_for("modules"))


@app.route("/deactivate_module/<int:id>")
def deactivate_module(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    module = db_session.query(Module).filter_by(id=id).first()
    if module:
        module.status = "Inactive"
        db_session.commit()
        flash("Module deactivated successfully.", "success")
    return redirect(url_for("modules"))


# ==================================================
# TEACHER MANAGEMENT (ADMIN) - FIXED
# ==================================================

@app.route("/teachers", methods=["GET", "POST"])
def teachers():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        fullname = request.form.get("fullname")
        phone = request.form.get("phone")
        email = request.form.get("email")
        password = request.form.get("password")
        status = request.form.get("status")
        specialization = request.form.get("specialization", "")

        # Check if email exists
        existing = db_session.query(User).filter_by(email=email).first()
        if existing:
            flash("Email already exists.", "warning")
            return redirect(url_for("teachers"))

        # Create the user FIRST
        user = User(
            fullname=fullname,
            phone=phone,
            email=email,
            password=password,
            role="teacher",
            status=status
        )
        db_session.add(user)
        db_session.flush()  # This gets the user.id
        
        # Create the teacher WITH the user_id
        teacher = Teacher(
            user_id=user.id,  # CRITICAL: Link to the user
            fullname=fullname,
            email=email,
            phone=phone,
            specialization=specialization,
            status=status
        )
        db_session.add(teacher)
        db_session.commit()
        
        flash("Teacher added successfully.", "success")
        return redirect(url_for("teachers"))

    search = request.args.get("search", "").strip()
    teachers = db_session.query(Teacher).all()

    return render_template("admin/teachers.html", teachers=teachers, search=search)


@app.route('/edit_teacher/<int:id>', methods=['GET', 'POST'])
def edit_teacher(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    teacher = db_session.query(Teacher).filter_by(id=id).first()
    if not teacher:
        flash("Teacher not found.", "danger")
        return redirect(url_for("teachers"))

    # Find the associated user
    user = db_session.query(User).filter_by(email=teacher.email, role="teacher").first()
    
    # If user not found by email, try by user_id
    if not user and teacher.user_id:
        user = db_session.query(User).filter_by(id=teacher.user_id, role="teacher").first()

    if request.method == "POST":
        teacher.fullname = request.form.get('fullname')
        teacher.email = request.form.get('email')
        teacher.phone = request.form.get('phone')
        teacher.specialization = request.form.get('specialization')
        teacher.status = request.form.get('status')

        if user:
            user.fullname = request.form.get('fullname')
            user.email = request.form.get('email')
            user.phone = request.form.get('phone')
            user.status = request.form.get('status')
            # Make sure user_id is set correctly
            teacher.user_id = user.id

        db_session.commit()
        flash("Teacher updated successfully!", "success")
        return redirect(url_for('teachers'))

    return render_template("admin/edit_teacher.html", teacher=teacher, user=user)


@app.route('/delete_teacher/<int:id>')
def delete_teacher(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    teacher = db_session.query(Teacher).filter_by(id=id).first()
    if not teacher:
        flash("Teacher not found.", "danger")
        return redirect(url_for("teachers"))

    try:
        # Find the associated user
        user = None
        
        # Try by user_id first
        if teacher.user_id:
            user = db_session.query(User).filter_by(id=teacher.user_id, role="teacher").first()
        
        # If not found by user_id, try by email
        if not user:
            user = db_session.query(User).filter_by(email=teacher.email, role="teacher").first()
            if user:
                # Update teacher with correct user_id before deletion
                teacher.user_id = user.id
                db_session.flush()
        
        # Delete the user first (if exists)
        if user:
            db_session.delete(user)
        
        # Then delete the teacher
        db_session.delete(teacher)
        db_session.commit()
        
        flash("Teacher deleted successfully.", "success")
    except Exception as e:
        db_session.rollback()
        flash(f"Error deleting teacher: {str(e)}", "danger")
    
    return redirect(url_for('teachers'))


# ==================================================
# ADMIN FIX - Fix teacher user_id links
# ==================================================

@app.route("/admin/fix_teachers")
def fix_teachers():
    """One-time fix to ensure all teachers have correct user_id links"""
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))
    
    fixed_count = 0
    error_count = 0
    teachers = db_session.query(Teacher).all()
    
    for teacher in teachers:
        try:
            # Check if teacher has a user_id
            if not teacher.user_id:
                # Try to find user by email
                user = db_session.query(User).filter_by(
                    email=teacher.email,
                    role="teacher"
                ).first()
                
                if user:
                    teacher.user_id = user.id
                    fixed_count += 1
                    print(f"Fixed teacher: {teacher.fullname} -> user_id: {user.id}")
                else:
                    # Create a user for this teacher
                    print(f"Creating user for teacher: {teacher.fullname}")
                    user = User(
                        fullname=teacher.fullname,
                        email=teacher.email,
                        phone=teacher.phone,
                        password="password123",  # Default password
                        role="teacher",
                        status=teacher.status or "Active"
                    )
                    db_session.add(user)
                    db_session.flush()
                    teacher.user_id = user.id
                    fixed_count += 1
            
            # Verify the user_id actually exists
            elif teacher.user_id:
                user = db_session.query(User).filter_by(id=teacher.user_id).first()
                if not user:
                    # user_id doesn't exist, try to find by email
                    user = db_session.query(User).filter_by(
                        email=teacher.email,
                        role="teacher"
                    ).first()
                    if user:
                        teacher.user_id = user.id
                        fixed_count += 1
                        print(f"Fixed teacher: {teacher.fullname} -> user_id: {user.id}")
        except Exception as e:
            error_count += 1
            print(f"Error fixing teacher {teacher.id}: {str(e)}")
    
    db_session.commit()
    flash(f"Fixed {fixed_count} teacher records. {error_count} errors.", "success")
    return redirect(url_for("teachers"))


# ==================================================
# ==================================================
# TEACHER SECTION - COMPLETELY FIXED
# ==================================================
# ==================================================

# ==================================================
# TEACHER DASHBOARD - COMPLETELY FIXED
# ==================================================

@app.route("/teacher_dashboard")
def teacher_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "teacher":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    # Get the logged-in user
    user = db_session.query(User).filter_by(id=session["user_id"]).first()
    
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("login"))
    
    # Find teacher by user_id (most reliable)
    teacher = db_session.query(Teacher).filter_by(user_id=user.id).first()
    
    if not teacher:
        # Fallback: try by email (exact match)
        teacher = db_session.query(Teacher).filter_by(email=user.email).first()
        
        if teacher:
            # FIX: Update the teacher record with the correct user_id
            teacher.user_id = user.id
            db_session.commit()
            flash("Teacher profile fixed. Please refresh.", "info")
            return redirect(url_for("teacher_dashboard"))
        
        if not teacher:
            flash("Teacher profile not found. Please contact admin.", "danger")
            return redirect(url_for("login"))
    
    # Get ALL courses assigned to this specific teacher
    my_courses = db_session.query(Course).join(
        CourseTeacher,
        CourseTeacher.course_id == Course.id
    ).filter(
        CourseTeacher.teacher_id == teacher.id,
        CourseTeacher.status == "Active"
    ).all()
    
    # Count statistics for this teacher's courses only
    total_students = 0
    total_free_students = 0
    total_paid_students = 0
    total_modules = 0
    total_assignments = 0
    pending_submissions = 0
    pending_questions = 0
    
    for course in my_courses:
        # Count students for each course (only active enrollments)
        if course.is_free:
            students = db_session.query(Enrollment).filter_by(
                course_id=course.id,
                status="Active"
            ).count()
            total_free_students += students
        else:
            students = db_session.query(Enrollment).filter_by(
                course_id=course.id,
                status="Active",
                payment_status="Paid"
            ).count()
            total_paid_students += students
        
        total_students += students
        
        # Count modules
        module_count = db_session.query(Module).filter_by(
            course_id=course.id,
            status="Active"
        ).count()
        total_modules += module_count
        
        # Count assignments
        assignment_count = db_session.query(Assignment).filter_by(
            course_id=course.id,
            status="Active"
        ).count()
        total_assignments += assignment_count
        
        # Count pending submissions
        pending_count = db_session.query(AssignmentSubmission).join(
            Assignment
        ).filter(
            Assignment.course_id == course.id,
            AssignmentSubmission.status == "Submitted"
        ).count()
        pending_submissions += pending_count
        
        # Count pending questions
        question_count = db_session.query(Question).filter_by(
            course_id=course.id,
            status="Pending"
        ).count()
        pending_questions += question_count
    
    return render_template(
        "teacher/teacher_dashboard.html",
        email=session["email"],
        teacher=teacher,
        my_courses=my_courses,
        total_students=total_students,
        total_free_students=total_free_students,
        total_paid_students=total_paid_students,
        total_modules=total_modules,
        total_assignments=total_assignments,
        pending_submissions=pending_submissions,
        pending_questions=pending_questions
    )


# ==================================================
# TEACHER - MANAGE COURSE - With Authorization Check
# ==================================================

@app.route("/teacher/manage_course/<int:course_id>")
def manage_course_modules(course_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "teacher":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))
    
    # Get the teacher
    user = db_session.query(User).filter_by(id=session["user_id"]).first()
    teacher = db_session.query(Teacher).filter_by(user_id=user.id).first()
    
    if not teacher:
        flash("Teacher profile not found.", "danger")
        return redirect(url_for("login"))
    
    # IMPORTANT: Check if this course is assigned to this teacher
    assignment = db_session.query(CourseTeacher).filter_by(
        course_id=course_id,
        teacher_id=teacher.id,
        status="Active"
    ).first()
    
    if not assignment:
        flash("You are not authorized to manage this course.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    course = db_session.query(Course).filter_by(id=course_id).first()
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    modules = db_session.query(Module).filter_by(
        course_id=course_id
    ).order_by(Module.module_number).all()
    
    assignments = db_session.query(Assignment).filter_by(
        course_id=course_id
    ).order_by(Assignment.id.desc()).all()
    
    quizzes = db_session.query(Quiz).filter_by(
        course_id=course_id
    ).order_by(Quiz.id.desc()).all()
    
    # For paid courses, only count paid students
    # For free courses, count all enrolled students
    if course.is_free:
        enrolled_students = db_session.query(Enrollment).filter_by(
            course_id=course_id,
            status="Active"
        ).all()
    else:
        enrolled_students = db_session.query(Enrollment).filter_by(
            course_id=course_id,
            status="Active",
            payment_status="Paid"
        ).all()
    
    for assignment in assignments:
        assignment.submission_count = db_session.query(AssignmentSubmission).filter_by(
            assignment_id=assignment.id
        ).count()
        assignment.graded_count = db_session.query(AssignmentSubmission).filter_by(
            assignment_id=assignment.id,
            status="Graded"
        ).count()
    
    for quiz in quizzes:
        quiz.attempt_count = db_session.query(QuizAttempt).filter_by(
            quiz_id=quiz.id
        ).count()
    
    return render_template(
        "teacher/manage_course.html",
        course=course,
        modules=modules,
        assignments=assignments,
        quizzes=quizzes,
        enrolled_students=enrolled_students,
        is_free=course.is_free
    )


# ==================================================
# TEACHER - ADD MODULE - With Authorization Check
# ==================================================

@app.route("/teacher/add_module/<int:course_id>", methods=["GET", "POST"])
def teacher_add_module(course_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "teacher":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))
    
    # Get the teacher
    user = db_session.query(User).filter_by(id=session["user_id"]).first()
    teacher = db_session.query(Teacher).filter_by(user_id=user.id).first()
    
    if not teacher:
        flash("Teacher profile not found.", "danger")
        return redirect(url_for("login"))
    
    # Check authorization
    assignment = db_session.query(CourseTeacher).filter_by(
        course_id=course_id,
        teacher_id=teacher.id,
        status="Active"
    ).first()
    
    if not assignment:
        flash("You are not authorized to manage this course.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    course = db_session.query(Course).filter_by(id=course_id).first()
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    if request.method == "POST":
        module_number = request.form.get("module_number")
        title = request.form.get("title")
        description = request.form.get("description")
        content = request.form.get("content")
        status = request.form.get("status", "Active")
        
        existing = db_session.query(Module).filter_by(
            course_id=course_id,
            module_number=module_number
        ).first()
        
        if existing:
            flash(f"Module {module_number} already exists.", "warning")
            return redirect(url_for("manage_course_modules", course_id=course_id))
        
        pdf_file = None
        pdf_upload = request.files.get("pdf_file")
        if pdf_upload and pdf_upload.filename:
            if not pdf_upload.filename.lower().endswith(".pdf"):
                flash("PDF file must be in PDF format.", "danger")
                return redirect(url_for("manage_course_modules", course_id=course_id))
            
            filename = secure_filename(pdf_upload.filename)
            pdf_folder = os.path.join(app.config["UPLOAD_FOLDER"], "pdfs")
            os.makedirs(pdf_folder, exist_ok=True)
            pdf_upload.save(os.path.join(pdf_folder, filename))
            pdf_file = filename

        video_file = None
        video_upload = request.files.get("video_file")
        if video_upload and video_upload.filename:
            if not allowed_file(video_upload.filename):
                flash("Invalid video format.", "danger")
                return redirect(url_for("manage_course_modules", course_id=course_id))
            
            filename = secure_filename(video_upload.filename)
            video_folder = os.path.join(app.config["UPLOAD_FOLDER"], "videos")
            os.makedirs(video_folder, exist_ok=True)
            video_upload.save(os.path.join(video_folder, filename))
            video_file = filename
        
        meeting_link = request.form.get("meeting_link")
        
        module = Module(
            course_id=course_id,
            module_number=module_number,
            title=title,
            description=description,
            content=content,
            pdf_file=pdf_file,
            video_file=video_file,
            meeting_link=meeting_link,
            status=status
        )
        
        db_session.add(module)
        db_session.commit()
        
        flash("Module added successfully!", "success")
        return redirect(url_for("manage_course_modules", course_id=course_id))
    
    return render_template("teacher/add_module.html", course=course)


# ==================================================
# TEACHER - EDIT MODULE - With Authorization Check
# ==================================================

@app.route("/teacher/edit_module/<int:module_id>", methods=["GET", "POST"])
def teacher_edit_module(module_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "teacher":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))
    
    module = db_session.query(Module).filter_by(id=module_id).first()
    if not module:
        flash("Module not found.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    # Get the teacher
    user = db_session.query(User).filter_by(id=session["user_id"]).first()
    teacher = db_session.query(Teacher).filter_by(user_id=user.id).first()
    
    if not teacher:
        flash("Teacher profile not found.", "danger")
        return redirect(url_for("login"))
    
    # Check authorization for the course this module belongs to
    assignment = db_session.query(CourseTeacher).filter_by(
        course_id=module.course_id,
        teacher_id=teacher.id,
        status="Active"
    ).first()
    
    if not assignment:
        flash("You are not authorized to edit this module.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    if request.method == "POST":
        module.module_number = request.form.get("module_number")
        module.title = request.form.get("title")
        module.description = request.form.get("description")
        module.content = request.form.get("content")
        module.status = request.form.get("status")
        
        pdf_upload = request.files.get("pdf_file")
        if pdf_upload and pdf_upload.filename:
            if not pdf_upload.filename.lower().endswith(".pdf"):
                flash("PDF file must be in PDF format.", "danger")
                return redirect(url_for("manage_course_modules", course_id=module.course_id))
            
            filename = secure_filename(pdf_upload.filename)
            pdf_folder = os.path.join(app.config["UPLOAD_FOLDER"], "pdfs")
            os.makedirs(pdf_folder, exist_ok=True)
            pdf_upload.save(os.path.join(pdf_folder, filename))
            module.pdf_file = filename

        video_upload = request.files.get("video_file")
        if video_upload and video_upload.filename:
            if not allowed_file(video_upload.filename):
                flash("Invalid video format.", "danger")
                return redirect(url_for("manage_course_modules", course_id=module.course_id))
            
            filename = secure_filename(video_upload.filename)
            video_folder = os.path.join(app.config["UPLOAD_FOLDER"], "videos")
            os.makedirs(video_folder, exist_ok=True)
            video_upload.save(os.path.join(video_folder, filename))
            module.video_file = filename
        
        meeting_link = request.form.get("meeting_link")
        if meeting_link:
            module.meeting_link = meeting_link
        
        db_session.commit()
        flash("Module updated successfully!", "success")
        return redirect(url_for("manage_course_modules", course_id=module.course_id))
    
    return render_template("teacher/edit_module.html", module=module)


# ==================================================
# TEACHER - DELETE MODULE - With Authorization Check
# ==================================================

@app.route("/teacher/delete_module/<int:module_id>")
def teacher_delete_module(module_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "teacher":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))
    
    module = db_session.query(Module).filter_by(id=module_id).first()
    if not module:
        flash("Module not found.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    # Get the teacher
    user = db_session.query(User).filter_by(id=session["user_id"]).first()
    teacher = db_session.query(Teacher).filter_by(user_id=user.id).first()
    
    if not teacher:
        flash("Teacher profile not found.", "danger")
        return redirect(url_for("login"))
    
    # Check authorization
    assignment = db_session.query(CourseTeacher).filter_by(
        course_id=module.course_id,
        teacher_id=teacher.id,
        status="Active"
    ).first()
    
    if not assignment:
        flash("You are not authorized to delete this module.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    course_id = module.course_id
    db_session.delete(module)
    db_session.commit()
    
    flash("Module deleted successfully.", "success")
    return redirect(url_for("manage_course_modules", course_id=course_id))


# ==================================================
# TEACHER - ADD ASSIGNMENT - With Authorization Check
# ==================================================

@app.route("/teacher/add_assignment/<int:course_id>", methods=["GET", "POST"])
def teacher_add_assignment(course_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "teacher":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))
    
    # Get the teacher
    user = db_session.query(User).filter_by(id=session["user_id"]).first()
    teacher = db_session.query(Teacher).filter_by(user_id=user.id).first()
    
    if not teacher:
        flash("Teacher profile not found.", "danger")
        return redirect(url_for("login"))
    
    # Check authorization
    assignment = db_session.query(CourseTeacher).filter_by(
        course_id=course_id,
        teacher_id=teacher.id,
        status="Active"
    ).first()
    
    if not assignment:
        flash("You are not authorized to manage this course.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    course = db_session.query(Course).filter_by(id=course_id).first()
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    modules = db_session.query(Module).filter_by(course_id=course_id).all()
    
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        instructions = request.form.get("instructions")
        due_date = request.form.get("due_date")
        max_score = request.form.get("max_score", 100)
        module_id = request.form.get("module_id")
        status = request.form.get("status", "Active")
        
        assignment = Assignment(
            course_id=course_id,
            module_id=module_id if module_id else None,
            title=title,
            description=description,
            instructions=instructions,
            due_date=due_date,
            max_score=max_score,
            status=status
        )
        
        db_session.add(assignment)
        db_session.commit()
        
        flash("Assignment created successfully!", "success")
        return redirect(url_for("manage_course_modules", course_id=course_id))
    
    return render_template("teacher/add_assignment.html", course=course, modules=modules)


# ==================================================
# TEACHER - VIEW ASSIGNMENT SUBMISSIONS - With Authorization Check
# ==================================================

@app.route("/teacher/assignment_submissions/<int:assignment_id>")
def teacher_assignment_submissions(assignment_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "teacher":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))
    
    assignment = db_session.query(Assignment).filter_by(id=assignment_id).first()
    if not assignment:
        flash("Assignment not found.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    # Get the teacher
    user = db_session.query(User).filter_by(id=session["user_id"]).first()
    teacher = db_session.query(Teacher).filter_by(user_id=user.id).first()
    
    if not teacher:
        flash("Teacher profile not found.", "danger")
        return redirect(url_for("login"))
    
    # Check authorization
    course_assignment = db_session.query(CourseTeacher).filter_by(
        course_id=assignment.course_id,
        teacher_id=teacher.id,
        status="Active"
    ).first()
    
    if not course_assignment:
        flash("You are not authorized to view these submissions.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    submissions = db_session.query(AssignmentSubmission).filter_by(
        assignment_id=assignment_id
    ).all()
    
    return render_template(
        "teacher/assignment_submissions.html",
        assignment=assignment,
        submissions=submissions
    )


# ==================================================
# TEACHER - GRADE SUBMISSION - With Authorization Check
# ==================================================

@app.route("/teacher/grade_submission/<int:submission_id>", methods=["GET", "POST"])
def teacher_grade_submission(submission_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "teacher":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))
    
    submission = db_session.query(AssignmentSubmission).filter_by(id=submission_id).first()
    if not submission:
        flash("Submission not found.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    # Get the teacher
    user = db_session.query(User).filter_by(id=session["user_id"]).first()
    teacher = db_session.query(Teacher).filter_by(user_id=user.id).first()
    
    if not teacher:
        flash("Teacher profile not found.", "danger")
        return redirect(url_for("login"))
    
    # Check authorization
    assignment = db_session.query(Assignment).filter_by(id=submission.assignment_id).first()
    if assignment:
        course_assignment = db_session.query(CourseTeacher).filter_by(
            course_id=assignment.course_id,
            teacher_id=teacher.id,
            status="Active"
        ).first()
        
        if not course_assignment:
            flash("You are not authorized to grade this submission.", "danger")
            return redirect(url_for("teacher_dashboard"))
    
    if request.method == "POST":
        score = request.form.get("score")
        feedback = request.form.get("feedback")
        
        submission.score = score
        submission.feedback = feedback
        submission.status = "Graded"
        submission.graded_at = datetime.now()
        
        db_session.commit()
        
        flash("Submission graded successfully!", "success")
        return redirect(url_for("teacher_assignment_submissions", assignment_id=submission.assignment_id))
    
    return render_template("teacher/grade_submission.html", submission=submission)


# ==================================================
# TEACHER - CREATE QUIZ - With Authorization Check
# ==================================================

@app.route("/teacher/create_quiz/<int:course_id>", methods=["GET", "POST"])
def teacher_create_quiz(course_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "teacher":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))
    
    # Get the teacher
    user = db_session.query(User).filter_by(id=session["user_id"]).first()
    teacher = db_session.query(Teacher).filter_by(user_id=user.id).first()
    
    if not teacher:
        flash("Teacher profile not found.", "danger")
        return redirect(url_for("login"))
    
    # Check authorization
    course_assignment = db_session.query(CourseTeacher).filter_by(
        course_id=course_id,
        teacher_id=teacher.id,
        status="Active"
    ).first()
    
    if not course_assignment:
        flash("You are not authorized to manage this course.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    course = db_session.query(Course).filter_by(id=course_id).first()
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    modules = db_session.query(Module).filter_by(course_id=course_id).all()
    
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        time_limit = request.form.get("time_limit", 30)
        passing_score = request.form.get("passing_score", 50)
        module_id = request.form.get("module_id")
        status = request.form.get("status", "Active")
        
        quiz = Quiz(
            course_id=course_id,
            module_id=module_id if module_id else None,
            title=title,
            description=description,
            time_limit=time_limit,
            passing_score=passing_score,
            status=status
        )
        
        db_session.add(quiz)
        db_session.commit()
        
        # Add questions
        question_count = int(request.form.get("question_count", 0))
        for i in range(question_count):
            question = request.form.get(f"question_{i}")
            option_a = request.form.get(f"option_a_{i}")
            option_b = request.form.get(f"option_b_{i}")
            option_c = request.form.get(f"option_c_{i}")
            option_d = request.form.get(f"option_d_{i}")
            correct_answer = request.form.get(f"correct_answer_{i}")
            points = request.form.get(f"points_{i}", 1)
            
            if question and option_a and option_b and correct_answer:
                quiz_question = QuizQuestion(
                    quiz_id=quiz.id,
                    question=question,
                    option_a=option_a,
                    option_b=option_b,
                    option_c=option_c,
                    option_d=option_d,
                    correct_answer=correct_answer,
                    points=points
                )
                db_session.add(quiz_question)
        
        db_session.commit()
        flash("Quiz created successfully!", "success")
        return redirect(url_for("manage_course_modules", course_id=course_id))
    
    return render_template(
        "teacher/create_quiz.html",
        course=course,
        modules=modules
    )


# ==================================================
# TEACHER - VIEW QUIZ ATTEMPTS - With Authorization Check
# ==================================================

@app.route("/teacher/quiz_attempts/<int:quiz_id>")
def teacher_quiz_attempts(quiz_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "teacher":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))
    
    quiz = db_session.query(Quiz).filter_by(id=quiz_id).first()
    if not quiz:
        flash("Quiz not found.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    # Get the teacher
    user = db_session.query(User).filter_by(id=session["user_id"]).first()
    teacher = db_session.query(Teacher).filter_by(user_id=user.id).first()
    
    if not teacher:
        flash("Teacher profile not found.", "danger")
        return redirect(url_for("login"))
    
    # Check authorization
    course_assignment = db_session.query(CourseTeacher).filter_by(
        course_id=quiz.course_id,
        teacher_id=teacher.id,
        status="Active"
    ).first()
    
    if not course_assignment:
        flash("You are not authorized to view these attempts.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    attempts = db_session.query(QuizAttempt).filter_by(
        quiz_id=quiz_id
    ).order_by(QuizAttempt.completed_at.desc()).all()
    
    return render_template(
        "teacher/quiz_attempts.html",
        quiz=quiz,
        attempts=attempts
    )


# ==================================================
# TEACHER - ANSWER QUESTION - With Authorization Check
# ==================================================

@app.route("/teacher/answer_question/<int:question_id>", methods=["GET", "POST"])
def teacher_answer_question(question_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "teacher":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))
    
    question = db_session.query(Question).filter_by(id=question_id).first()
    if not question:
        flash("Question not found.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    # Get the teacher
    user = db_session.query(User).filter_by(id=session["user_id"]).first()
    teacher = db_session.query(Teacher).filter_by(user_id=user.id).first()
    
    if not teacher:
        flash("Teacher profile not found.", "danger")
        return redirect(url_for("login"))
    
    # Check authorization - teacher should be assigned to the course
    course_assignment = db_session.query(CourseTeacher).filter_by(
        course_id=question.course_id,
        teacher_id=teacher.id,
        status="Active"
    ).first()
    
    if not course_assignment:
        flash("You are not authorized to answer questions for this course.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    if request.method == "POST":
        content = request.form.get("content")
        
        answer = Answer(
            question_id=question_id,
            user_id=session["user_id"],
            content=content
        )
        
        question.status = "Answered"
        
        db_session.add(answer)
        db_session.commit()
        
        flash("Answer posted successfully!", "success")
        return redirect(url_for("teacher_dashboard"))
    
    return render_template(
        "teacher/answer_question.html",
        question=question
    )


# ==================================================
# TEACHER - VIEW STUDENT PROGRESS - With Authorization Check
# ==================================================

@app.route("/teacher/student_progress/<int:course_id>")
def teacher_student_progress(course_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "teacher":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))
    
    # Get the teacher
    user = db_session.query(User).filter_by(id=session["user_id"]).first()
    teacher = db_session.query(Teacher).filter_by(user_id=user.id).first()
    
    if not teacher:
        flash("Teacher profile not found.", "danger")
        return redirect(url_for("login"))
    
    # Check authorization
    course_assignment = db_session.query(CourseTeacher).filter_by(
        course_id=course_id,
        teacher_id=teacher.id,
        status="Active"
    ).first()
    
    if not course_assignment:
        flash("You are not authorized to view progress for this course.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    course = db_session.query(Course).filter_by(id=course_id).first()
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("teacher_dashboard"))
    
    # For paid courses, only show paid students
    if course.is_free:
        enrollments = db_session.query(Enrollment).filter_by(
            course_id=course_id,
            status="Active"
        ).all()
    else:
        enrollments = db_session.query(Enrollment).filter_by(
            course_id=course_id,
            status="Active",
            payment_status="Paid"
        ).all()
    
    # Get all modules for this course
    modules = db_session.query(Module).filter_by(course_id=course_id).all()
    total_modules = len(modules)
    
    # Calculate progress for each student
    for enrollment in enrollments:
        completed_modules = db_session.query(StudentModuleProgress).filter_by(
            student_id=enrollment.student_id,
            status="Completed"
        ).count()
        enrollment.completion_percentage = (completed_modules / total_modules * 100) if total_modules > 0 else 0
    
    return render_template(
        "teacher/student_progress.html",
        course=course,
        enrollments=enrollments,
        is_free=course.is_free
    )


# ==================================================
# USER DASHBOARD (UNUSED)
# ==================================================

@app.route("/user_dashboard")
def user_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "user":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    return render_template("users/user_dashboard.html", email=session["email"])


# ==================================================
# RUN APPLICATION
# ==================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )