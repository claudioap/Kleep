import re
from datetime import datetime, time
from itertools import chain

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import models as djm
from django.contrib.auth.models import AbstractUser
from django.urls import reverse
from django.utils.timezone import make_aware
from django.conf import settings

import reversion
from imagekit.models import ImageSpecField
from markdownx.models import MarkdownxField
from markdownx.utils import markdownify
from pilkit.processors import SmartResize
from polymorphic.models import PolymorphicModel

from college.choice_types import WEEKDAY_CHOICES


def user_profile_pic_path(user, filename):
    return f'u/{user.id}/pic.{filename.split(".")[-1].lower()}'


class User(AbstractUser):
    nickname = djm.CharField(null=False, max_length=20, unique=True, verbose_name='Alcunha', db_index=True)
    last_nickname_change = djm.DateField(default=datetime(2000, 1, 1).date())
    birth_date = djm.DateField(null=True, blank=True, verbose_name='Nascimento')
    last_activity = djm.DateTimeField(auto_now_add=True)
    residence = djm.CharField(max_length=64, null=True, blank=True, verbose_name='Residência')
    picture = djm.ImageField(upload_to=user_profile_pic_path, null=True, blank=True, verbose_name='Foto')
    picture_medium = ImageSpecField(
        source='picture',
        processors=[SmartResize(*settings.MEDIUM_ICON_SIZE)],
        format='JPEG',
        options={'quality': settings.MEDIUM_QUALITY})
    picture_thumbnail = ImageSpecField(
        source='picture',
        processors=[SmartResize(*settings.SMALL_ICON_SIZE)],
        format='JPEG',
        options={'quality': settings.MEDIUM_QUALITY})
    webpage = djm.URLField(null=True, blank=True, verbose_name='Página pessoal')

    REQUIRED_FIELDS = ['email', 'nickname']

    NOBODY = 0
    FRIENDS = 1
    USERS = 2
    EVERYBODY = 3
    PROFILE_VISIBILITY_CHOICES = (
        (NOBODY, 'Ninguém'),
        (FRIENDS, 'Amigos'),
        (USERS, 'Utilizadores'),
        (EVERYBODY, 'Todos'))
    profile_visibility = djm.IntegerField(choices=PROFILE_VISIBILITY_CHOICES, default=0)
    info_visibility = djm.IntegerField(choices=PROFILE_VISIBILITY_CHOICES, default=0)
    about_visibility = djm.IntegerField(choices=PROFILE_VISIBILITY_CHOICES, default=0)
    social_visibility = djm.IntegerField(choices=PROFILE_VISIBILITY_CHOICES, default=0)
    groups_visibility = djm.IntegerField(choices=PROFILE_VISIBILITY_CHOICES, default=0)
    enrollments_visibility = djm.IntegerField(choices=PROFILE_VISIBILITY_CHOICES, default=0)
    schedule_visibility = djm.IntegerField(choices=PROFILE_VISIBILITY_CHOICES, default=0)

    MALE = 0
    FEMALE = 1
    OTHER = 2

    GENDER_CHOICES = (
        (MALE, 'Homem'),
        (FEMALE, 'Mulher'),
        (OTHER, 'Outro')
    )
    gender = djm.IntegerField(choices=GENDER_CHOICES, null=True, blank=True)
    about = MarkdownxField(blank=True, null=True)
    permissions_overridden = djm.BooleanField(default=False)
    # Cached fields
    is_student = djm.BooleanField(default=False)
    is_teacher = djm.BooleanField(default=False)
    course = djm.ForeignKey('college.Course', on_delete=djm.CASCADE, null=True, blank=True, default=None)
    points = djm.IntegerField(default=0)

    class Meta:
        permissions = [
            ('student_access', 'Can browse the system as a student.'),
            ('teacher_access', 'Can browse the system as a teacher.'),
        ]

    def __str__(self):
        return self.nickname

    def get_absolute_url(self):
        return reverse('users:profile', args=[self.nickname])

    @property
    def name(self):
        if self.first_name:
            return self.get_full_name()
        return self.nickname

    @property
    def about_html(self):
        return markdownify(self.about)

    def updated_cached(self):
        changed = False
        is_student = self.students.exists()
        if self.is_student != is_student:
            self.is_student = is_student
            changed = True
        is_teacher = self.teachers.exists()
        if self.is_teacher != is_teacher:
            self.is_teacher = is_teacher
            changed = True
        course_candidates = set()

        for student in self.students.filter(last_year=settings.COLLEGE_YEAR).all():
            if student.course:
                course_candidates.add(student.course)
        if len(course_candidates) == 1:
            self.course = course_candidates.pop()
            changed = True

        if changed:
            self.save()

    def profile_permissions_for(self, user):
        permissions = {
            'profile_visibility': False,
            'info_visibility': False,
            'about_visibility': False,
            'social_visibility': False,
            'groups_visibility': False,
            'enrollments_visibility': False,
            'schedule_visibility': False}

        # Owner and staff can do everything
        if self == user or user.is_staff:
            for permission in permissions.keys():
                permissions[permission] = True
            permissions['checksum'] = (1 << len(permissions)) - 1
            return permissions

        # Without profile visibility most people can do nothing
        if not (self.profile_visibility == User.EVERYBODY
                or (self.profile_visibility == User.USERS and not user.is_anonymous)):
            permissions['checksum'] = 0
            return permissions

        # Calculate for others
        checksum = 0
        for i, permission_name in enumerate(list(permissions.keys())):
            permission = getattr(self, permission_name)
            if permission == User.EVERYBODY or (permission == User.USERS and not user.is_anonymous):
                permissions[permission_name] = True
                checksum = checksum + (1 << i)
        permissions['checksum'] = checksum
        return permissions

    def calculate_missing_info(self):
        # Set a name if none is known
        for entity in chain(self.teachers.all(), self.students.all()):
            if (self.first_name is None or self.first_name.strip() == '') and entity.name:
                names = entity.name.split()
                self.first_name = names[0]
                if len(names) > 1:
                    self.last_name = ' '.join(names[1:])
                self.save()

    def clear_notification_cache(self):
        cache.delete_many(['%s_notification_count' % self.id, '%s_notification_list' % self.id])


def award_pic_path(award, filename):
    return f'badges/pic.{filename.split(".")[-1].lower()}'


class Award(djm.Model):
    name = djm.CharField(max_length=32, unique=True)
    style = djm.CharField(max_length=15, null=True, default=None)
    points = djm.IntegerField(default=0)
    users = djm.ManyToManyField(User, through='UserAward', related_name='awards')
    picture = djm.ImageField(upload_to=award_pic_path, null=True)
    picture_icon = ImageSpecField(
        source='picture',
        processors=[SmartResize(*settings.MEDIUM_ICON_SIZE)],
        format='PNG')


class UserAward(djm.Model):
    user = djm.ForeignKey(User, on_delete=djm.CASCADE)
    award = djm.ForeignKey(Award, on_delete=djm.PROTECT)
    receive_date = djm.DateField(auto_created=True)


class ExternalPage(djm.Model):
    GITLAB = 0
    GITHUB = 1
    GITEA = 2
    MASTODON = 3
    DIASPORA = 4
    PEERTUBE = 5
    VIMEO = 6
    DEVIANTART = 7
    FLICKR = 8
    THINGIVERSE = 9
    WIKIPEDIA = 10
    OTHER = 1000

    PLATFORM_CHOICES = (
        (GITLAB, 'GitLab'),
        (GITHUB, 'GitHub'),
        (MASTODON, 'Mastodon'),
        (DIASPORA, 'Diaspora'),
        (PEERTUBE, 'Peertube'),
        (VIMEO, 'Vimeo'),
        (DEVIANTART, 'DeviantArt'),
        (FLICKR, 'Flickr'),
        (THINGIVERSE, 'Thingiverse'),
        (WIKIPEDIA, 'Wikipedia'),
        (OTHER, 'Outro'),
    )

    user = djm.ForeignKey(User, on_delete=djm.CASCADE, related_name='external_pages')
    #: The platform this page matched with
    platform = djm.IntegerField(choices=PLATFORM_CHOICES, null=True, blank=True)
    #: Ideally the username in profile pages
    name = djm.CharField(max_length=64, null=True, blank=True)
    #: The page URL
    url = djm.URLField(max_length=128, unique=True)

    def __str__(self):
        return f'{self.get_platform_display()}: {self.url}'

    url_exp = re.compile("^(http[s]?://)?((\w+\.)*(?P<domain>\w+\.\w+))(/.*)$")
    known_domains = {
        'gitlab.com': GITLAB,
        'github.com': GITHUB,
        'mastodon.social': MASTODON,
        'vimeo.com': VIMEO,
        'deviantart.com': DEVIANTART,
        'flickr.com': FLICKR,
        'thingiverse.com': THINGIVERSE,
        'wikipedia.org': WIKIPEDIA,
    }

    def save(self, *args, **kwargs):
        if self.platform is None:
            match = ExternalPage.url_exp.match(self.url)
            if match:
                domain = match.group('domain')
                if domain in ExternalPage.known_domains:
                    self.platform = ExternalPage.known_domains[domain]
        super(ExternalPage, self).save(*args, **kwargs)

    @property
    def title_short(self):
        if self.name:
            return f'{self.name[:27]}...' if len(self.name) > 30 else self.name
        return f'{self.url[:27]}...' if len(self.url) > 30 else self.url


class Registration(djm.Model):
    #: Email that is being used to register
    email = djm.EmailField()
    #: Claimed username
    username = djm.CharField(verbose_name='utilizador', max_length=128)
    #: Claimed nickname
    nickname = djm.CharField(verbose_name='alcunha', blank=True, max_length=128)
    #: Hash of the password
    password = djm.CharField(verbose_name='palavra-passe', max_length=128)
    #: Student that this registration is claiming
    requested_student = djm.ForeignKey(
        'college.Student',
        null=True,
        blank=True,
        on_delete=djm.CASCADE,
        related_name='registrations')
    #: Teacher that this registration is claiming
    requested_teacher = djm.ForeignKey(
        'college.Teacher',
        null=True,
        blank=True,
        on_delete=djm.CASCADE,
        related_name='registrations')
    #: User to which this registration led
    resulting_user = djm.OneToOneField('User', null=True, blank=True, on_delete=djm.CASCADE)
    #: Creation timestamp
    creation = djm.DateTimeField(auto_now_add=True)
    #: Validation token
    token = djm.CharField(max_length=16)
    #: Number of validation attempts
    failed_attempts = djm.IntegerField(default=0)

    def __str__(self):
        return f"{self.username}/{self.nickname}/{self.requested_student}/{self.requested_teacher} -{self.email}"


class VulnerableHash(djm.Model):
    hash = djm.TextField()

    class Meta:
        # TODO figure how to assign to a database
        managed = False
        db_table = 'Hashes'


class Invite(djm.Model):
    """A invite issued by an used to allow other :py:class:`User` to register"""
    #: The :py:class:`User` that issued the invite
    issuer = djm.ForeignKey(User, on_delete=djm.PROTECT, related_name='invites')
    #: The token that is used to activate the invite
    token = djm.CharField(max_length=16, unique=True)
    #: Date on which the invite was created
    created = djm.DateTimeField(auto_now_add=True)
    #: Date after which the invite is no longer valid
    expiration = djm.DateTimeField()
    #: :py:class:`Registration` that used the invite
    # FIXME Invite rendered useless if another registration conflicts with this one before it is confirmed.
    registration = djm.OneToOneField(Registration, null=True, on_delete=djm.SET_NULL)
    #: :py:class:`User` that resulted from the usage of this invite TODO deprecate
    resulting_user = djm.OneToOneField(User, null=True, blank=True, on_delete=djm.SET_NULL)
    #: Whether the invite got revoked
    revoked = djm.BooleanField(default=False)

    def __str__(self):
        return f"{self.issuer.nickname}:{self.token}"

    @property
    def expired(self):
        return self.expiration < make_aware(datetime.now(), is_dst=True)


class Subscription(djm.Model):
    """
    User subscription to an object. Used for tasks such as notification delivery.
    """
    #: ContentType of the subscribable object that is targeted by this subscription
    to_content_type = djm.ForeignKey(ContentType, on_delete=djm.CASCADE)
    #: Id of the subscribable object that is targeted by this subscription
    to_object_id = djm.PositiveIntegerField()
    #: Subscribable object that this subscription targets
    to = GenericForeignKey('to_content_type', 'to_object_id')
    #: :py:class:`users.models.User` that wishes to be notified.
    subscriber = djm.ForeignKey(User, on_delete=djm.CASCADE, related_name='subscriptions')
    #: Datetime at which the activity happened
    issue_timestamp = djm.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['to_content_type', 'to_object_id', 'subscriber']

    def __str__(self):
        return f'{self.issue_timestamp}({self.to})'


@reversion.register()
class Activity(PolymorphicModel):
    """An activity is an action taken by a user at a given point in time."""
    #: :py:class:`User` that made this activity.
    user = djm.ForeignKey(User, on_delete=djm.CASCADE, related_name='activities')
    #: The id field, but renamed to avoid collisions upon multiple inheritance
    activity_id = djm.AutoField(primary_key=True, db_index=True)
    #: Datetime at which the activity happened
    timestamp = djm.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.timestamp}({self.user})'

    class Meta:
        verbose_name_plural = "activities"


class Notification(PolymorphicModel):
    """A notification points to unknown past actions with a particular relevance."""
    #: :py:class:`users.models.User` that received the notification.
    receiver = djm.ForeignKey(User, on_delete=djm.CASCADE, related_name='notifications')
    #: Datetime at which the notification was issued
    issue_timestamp = djm.DateTimeField(auto_now_add=True)
    #: Whether the notification has been seen
    dismissed = djm.BooleanField(default=False)

    def __str__(self):
        return f'{self.issue_timestamp}({self.receiver})'

    def to_api(self):
        return {
            'id': self.id,
            'message': None,
            'timestamp': self.issue_timestamp.strftime('%y/%-m/%-d %H:%M'),
            'type': None,
            'entity': None,
            'url': None}


class GenericNotification(Notification):
    """Some generic text notification."""
    #: The message that will be presented with this notification.
    message = djm.TextField()

    def __str__(self):
        return f'{self.issue_timestamp}({self.receiver}): {self.message}'

    def to_api(self):
        result = super(GenericNotification, self).to_api()
        result['message'] = self.message
        return result


class ScheduleEntry(PolymorphicModel):
    """Base entry in this :py:class:`User` 's personal activity schedule."""
    #: :py:class:`User` with this entry
    user = djm.ForeignKey(User, on_delete=djm.CASCADE, related_name='schedule_entries')
    #: Title for the entry
    title = djm.CharField(max_length=128)
    #: (Optional) Textual information associated with the entry
    note = djm.TextField(blank=True, null=True)
    #: Whether the entry occurrence scheduling is cancelled
    revoked = djm.BooleanField(default=False)

    class Meta:
        verbose_name_plural = 'schedule entries'


class ScheduleOnce(ScheduleEntry):
    """Represents a one-time entry in this :py:class:`User` 's activity schedule."""
    #: The date at which this event is set to happen
    datetime = djm.DateTimeField()
    #: The predicted duration of this event interval
    duration = djm.IntegerField()

    def __str__(self):
        return f"{self.title}, dia {datetime.strftime(self.datetime, '%d/%m/%Y %H:%M')}"


class SchedulePeriodic(ScheduleEntry):
    """Represents a periodic entry in this group's activity schedule. This entry happens weekly."""
    #: The weekday on which this event is set to happen
    weekday = djm.IntegerField(choices=WEEKDAY_CHOICES)
    #: The time at which the event occurs.
    time = djm.TimeField()
    #: The predicted duration of these recurring timeline
    duration = djm.IntegerField()
    #: The date on which this scheduling was defined to start
    start_date = djm.DateField()
    #: The date on which this scheduling lost its validity
    end_date = djm.DateField(blank=True, null=True, default=None)

    def __str__(self):
        return f"{self.title}, {self.get_weekday_display()} ás {time.strftime(self.time, '%H:%M')}"


class ReputationOffset(PolymorphicModel):
    """An award or penalization with effect in an user's reputation points."""
    #: :py:class:`users.models.User` that received the award.
    receiver = djm.ForeignKey(User, on_delete=djm.CASCADE, related_name='point_offsets')
    #: Datetime at which the notification was issued
    issue_timestamp = djm.DateTimeField(auto_now_add=True)
    #: Amount of points being given
    amount = djm.IntegerField()
    #: Reason
    reason = djm.CharField(max_length=300, null=True)

    def __str__(self):
        return f'{self.issue_timestamp}({self.receiver})'

    def issue_notification(self):
        ReputationOffsetNotification.objects.create(reputation_offset=self, receiver=self.receiver)


class ReputationOffsetNotification(Notification):
    """Notification generated when a reputation offset is issued."""
    #: The message that will be presented with this notification.
    reputation_offset = djm.ForeignKey(ReputationOffset, on_delete=djm.CASCADE)

    def __str__(self):
        points = self.reputation_offset.amount
        if reason := self.reputation_offset.reason:
            if points < 0:
                return f'Penalização de {points} pontos: {reason}.'
            else:
                return f'Atribuição de {points} pontos: {reason}.'
        else:
            if points < 0:
                return f'Penalização de {points} pontos.'
            else:
                return f'Atribuição de {points} pontos.'

    def to_api(self):
        result = super(ReputationOffsetNotification, self).to_api()
        result['message'] = str(self)
        result['url'] = reverse('users:reputation', args=[self.reputation_offset.receiver.nickname])
        return result
