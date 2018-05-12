import random
import smtplib
import string
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from clip.models import Student as ClipStudent
from college.models import Student
from kleep.settings import EMAIL_SERVER, EMAIL_ACCOUNT, EMAIL_PASSWORD, REGISTRATIONS_ATTEMPTS_TOKEN, \
    REGISTRATIONS_TIMEWINDOW, REGISTRATIONS_TOKEN_LENGTH
from users.exceptions import InvalidToken, InvalidUsername, ExpiredRegistration, \
    AccountExists, AssignedStudent
from users.models import User, Registration


def pre_register(data: Registration):
    username = data.username
    nickname = data.nickname
    if ClipStudent.objects.filter(Q(internal_id=username) | Q(abbreviation=username)) \
            .exclude(data.student).exists():
        raise InvalidUsername(f'The username {username} matches a CLIP ID.')

    if User.objects.filter(Q(username=username) | Q(nickname=nickname)).exists():
        raise AccountExists(f'There is already an account with the username {username} or the nickname {nickname}.')

    # Delete any existing registration request for this user
    Registration.objects.filter(student=data.student).delete()

    if hasattr(data.student, 'student'):
        user = data.student.student.user  # Registration -> clip_student -> student -> user
        if user is not None:
            raise AssignedStudent(f'The student {username} is already assigned to the account {user}.')

    token = generate_token(REGISTRATIONS_TOKEN_LENGTH)
    send_mail(data.email, token)
    data.token = token
    data.save()


def validate_token(email, token) -> User:
    registration = Registration.objects.filter(email=email)
    if registration.exists():
        registration = registration.order_by('creation').reverse().first()
    else:
        raise ExpiredRegistration('Não foi possível encontrar um registo com este email.')
    if registration.token == token:  # Correct token
        elapsed_minutes = (timezone.now() - registration.creation).seconds / 60
        if elapsed_minutes < REGISTRATIONS_TIMEWINDOW:
            registration.delete()
            raise ExpiredRegistration('O registo foi validado após o tempo permitido.')

        user = User.objects.create_user(
            username=registration.username,
            email=registration.email,
            nickname=registration.nickname,
            last_activity=timezone.now()
        )
        clip_student = registration.student
        user.password = registration.password  # Copy hash
        user.save()
        student = student_from_clip_student(clip_student)
        student.confirmed = True
        student.user = user
        try:
            pass  # TODO populate student enrollments and turns
        finally:
            student.save()
        return user
    else:
        if registration.failed_attempts < REGISTRATIONS_ATTEMPTS_TOKEN - 1:
            registration.failed_attempts += 1
            registration.save()
            raise InvalidToken()
        else:
            registration.delete()
            raise InvalidToken(deleted=True)


def student_from_clip_student(clip_student: ClipStudent) -> Student:
    if hasattr(clip_student, 'student'):
        raise RuntimeError('Student already exists')
    student = Student(number=int(clip_student.internal_id), abbreviation=clip_student.abbreviation,
                      course=clip_student.course.course, clip_student=clip_student)
    student.save()
    return student


def generate_token(length: int) -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def send_mail(email, token):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "Link"
    msg['From'] = EMAIL_ACCOUNT
    msg['To'] = email

    # Create the body of the message (a plain-text and an HTML version).
    text = f"""
Olá. Penso que tentaste criar uma conta no Kleep. Se não foste tu então podes ignorar este email.\n
Por favor vai manualmente a <{reverse('', args=[])}> e insere o código {token}.\n
Este código só é valido na próxima hora.\n
"""
    html = f"""
    <html>
      <head></head>
      <body>
        <p>Olá. Penso que tentaste criar uma conta no Kleep. Se não foste tu então podes ignorar este email.</p>
        <p>Para concluires o registo carrega <a href="{reverse('', args=[])}">aqui</a>.</p>
        <p>Caso o link não seja um link, por favor vai manualmente a {reverse('', args=[])} e insere o código {token}.</p>
        <p style="font-size:0.8em">Este código só é valido na próxima hora.</p>
      </body>
    </html>
    """

    msg.attach(MIMEText(text, 'plain'))
    msg.attach(MIMEText(html, 'html'))

    server = smtplib.SMTP(EMAIL_SERVER, 587)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
    server.sendmail(EMAIL_ACCOUNT, email, msg.as_string())
    server.quit()