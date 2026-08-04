from sqlalchemy import Column, Integer, String, ForeignKey, Float, UniqueConstraint, Text, Boolean, DateTime, Numeric, func
from sqlalchemy.orm import relationship
from connections import Base
from datetime import datetime


# =====================================
# USERS TABLE
# =====================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fullname = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone = Column(String(20))
    password = Column(String(255), nullable=False)
    role = Column(String(20), default="student")  # admin, teacher, student
    status = Column(String(20), default="Active")
    profile_image = Column(String(255))
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    student = relationship("Student", back_populates="user", uselist=False, cascade="all, delete-orphan")
    teacher = relationship("Teacher", back_populates="user", uselist=False, cascade="all, delete-orphan")
    announcements = relationship("Announcement", back_populates="author", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="user", cascade="all, delete-orphan")
    answers = relationship("Answer", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


# =====================================
# STUDENTS TABLE
# =====================================

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    fullname = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone = Column(String(20))
    bio = Column(Text)
    status = Column(String(20), default="Pending")  # Pending, Approved, Blocked
    profile_completed = Column(Boolean, default=False)
    enrolled_date = Column(DateTime, default=datetime.now)

    # Relationships
    user = relationship("User", back_populates="student")
    enrollments = relationship("Enrollment", back_populates="student", cascade="all, delete-orphan")
    progress = relationship("StudentModuleProgress", back_populates="student", cascade="all, delete-orphan")
    submissions = relationship("AssignmentSubmission", back_populates="student", cascade="all, delete-orphan")
    quiz_attempts = relationship("QuizAttempt", back_populates="student", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="student", cascade="all, delete-orphan")
    answers = relationship("Answer", back_populates="student", cascade="all, delete-orphan")


# =====================================
# TEACHERS TABLE
# =====================================

class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    fullname = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone = Column(String(20))

    bio = Column(Text)
    status = Column(String(20), default="Active")
    joined_date = Column(DateTime, default=datetime.now)

    # Relationships
    user = relationship("User", back_populates="teacher")
    course_assignments = relationship("CourseTeacher", back_populates="teacher", cascade="all, delete-orphan")


# =====================================
# COURSES TABLE
# =====================================

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_name = Column(String(100), unique=True, nullable=False)
    course_code = Column(String(20), unique=True)
    duration = Column(String(50))
    fee = Column(Float, nullable=False, default=0.00)
    is_free = Column(Boolean, default=False)
    description = Column(Text)
    career_objectives = Column(Text)
    prerequisites = Column(Text)
    meeting_link = Column(String(500))
    status = Column(String(20), default="Active")
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    enrollments = relationship("Enrollment", back_populates="course", cascade="all, delete-orphan")
    modules = relationship("Module", back_populates="course", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="course", cascade="all, delete-orphan")
    quizzes = relationship("Quiz", back_populates="course", cascade="all, delete-orphan")
    announcements = relationship("Announcement", back_populates="course", cascade="all, delete-orphan")
    course_teachers = relationship("CourseTeacher", back_populates="course", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="course", cascade="all, delete-orphan")


# =====================================
# COURSE TEACHER ASSIGNMENT (Many-to-Many)
# =====================================

class CourseTeacher(Base):
    __tablename__ = "course_teachers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    assigned_date = Column(DateTime, default=datetime.now)
    status = Column(String(20), default="Active")

    # Relationships
    course = relationship("Course", back_populates="course_teachers")
    teacher = relationship("Teacher", back_populates="course_assignments")


# =====================================
# ENROLLMENTS TABLE
# =====================================

class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("student_id", "course_id", name="unique_student_course"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    date_enrolled = Column(DateTime, default=datetime.now)
    payment_status = Column(String(20), default="Pending")  # Pending, Paid, Verified
    status = Column(String(20), default="Active")
    completion_percentage = Column(Float, default=0)

    # Relationships
    student = relationship("Student", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")
    payments = relationship("Payment", back_populates="enrollment", cascade="all, delete-orphan")


# =====================================
# PAYMENTS TABLE
# =====================================

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    enrollment_id = Column(Integer, ForeignKey("enrollments.id"), nullable=False)
    amount = Column(Float, nullable=False)
    phone = Column(String(20))
    transaction_code = Column(String(100), unique=True)
    status = Column(String(20), default="Pending")  # Pending, Verified, Rejected
    verified_at = Column(DateTime)
    date_paid = Column(DateTime, default=datetime.now)

    # Relationships
    enrollment = relationship("Enrollment", back_populates="payments")


# =====================================
# MODULES TABLE
# =====================================

class Module(Base):
    __tablename__ = "modules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    module_number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    content = Column(Text)  # HTML content from editor
    pdf_file = Column(String(255))
    video_file = Column(String(255))
    meeting_link = Column(String(500))
    status = Column(String(20), default="Active")
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    course = relationship("Course", back_populates="modules")
    progress = relationship("StudentModuleProgress", back_populates="module", cascade="all, delete-orphan")


# =====================================
# STUDENT MODULE PROGRESS TABLE
# =====================================

class StudentModuleProgress(Base):
    __tablename__ = "student_module_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    module_id = Column(Integer, ForeignKey("modules.id"), nullable=False)
    status = Column(String(20), default="Not Started")  # Not Started, In Progress, Completed
    completed_date = Column(DateTime)
    time_spent = Column(Integer, default=0)  # Minutes spent

    # Relationships
    student = relationship("Student", back_populates="progress")
    module = relationship("Module", back_populates="progress")


# =====================================
# ASSIGNMENTS TABLE
# =====================================

class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    module_id = Column(Integer, ForeignKey("modules.id"), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    instructions = Column(Text)
    due_date = Column(DateTime)
    max_score = Column(Float, default=100)
    status = Column(String(20), default="Active")
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    course = relationship("Course", back_populates="assignments")
    submissions = relationship("AssignmentSubmission", back_populates="assignment", cascade="all, delete-orphan")


# =====================================
# ASSIGNMENT SUBMISSIONS TABLE
# =====================================

class AssignmentSubmission(Base):
    __tablename__ = "assignment_submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    file_name = Column(String(255))
    file_path = Column(String(500))
    submission_text = Column(Text)
    score = Column(Float, default=0)
    feedback = Column(Text)
    status = Column(String(20), default="Submitted")  # Submitted, Graded, Late, Resubmitted
    submitted_at = Column(DateTime, default=datetime.now)
    graded_at = Column(DateTime)

    # Relationships
    assignment = relationship("Assignment", back_populates="submissions")
    student = relationship("Student", back_populates="submissions")


# =====================================
# QUIZZES TABLE
# =====================================

class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    module_id = Column(Integer, ForeignKey("modules.id"), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    time_limit = Column(Integer, default=30)  # Minutes
    passing_score = Column(Float, default=50)
    status = Column(String(20), default="Active")
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    course = relationship("Course", back_populates="quizzes")
    questions = relationship("QuizQuestion", back_populates="quiz", cascade="all, delete-orphan")
    attempts = relationship("QuizAttempt", back_populates="quiz", cascade="all, delete-orphan")


# =====================================
# QUIZ QUESTIONS TABLE
# =====================================

class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    question = Column(Text, nullable=False)
    option_a = Column(String(500), nullable=False)
    option_b = Column(String(500), nullable=False)
    option_c = Column(String(500))
    option_d = Column(String(500))
    correct_answer = Column(String(10), nullable=False)  # A, B, C, D
    points = Column(Float, default=1)

    # Relationships
    quiz = relationship("Quiz", back_populates="questions")


# =====================================
# QUIZ ATTEMPTS TABLE
# =====================================

class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    score = Column(Float, default=0)
    passed = Column(Boolean, default=False)
    answers = Column(Text)  # JSON string of answers
    started_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime)

    # Relationships
    quiz = relationship("Quiz", back_populates="attempts")
    student = relationship("Student", back_populates="quiz_attempts")


# =====================================
# ANNOUNCEMENTS TABLE
# =====================================

class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    is_pinned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime)

    # Relationships
    course = relationship("Course", back_populates="announcements")
    author = relationship("User", back_populates="announcements")


# =====================================
# QUESTIONS TABLE
# =====================================

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(20), default="Pending")  # Pending, Answered, Closed
    is_public = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    course = relationship("Course", back_populates="questions")
    student = relationship("Student", back_populates="questions")
    user = relationship("User", back_populates="questions")
    answers = relationship("Answer", back_populates="question", cascade="all, delete-orphan")


# =====================================
# ANSWERS TABLE
# =====================================

class Answer(Base):
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    content = Column(Text, nullable=False)
    is_best = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    question = relationship("Question", back_populates="answers")
    user = relationship("User", back_populates="answers")
    student = relationship("Student", back_populates="answers")


# =====================================
# NOTIFICATIONS TABLE
# =====================================

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), default="info")  # info, success, warning, danger
    is_read = Column(Boolean, default=False)
    link = Column(String(500))
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    user = relationship("User", back_populates="notifications")