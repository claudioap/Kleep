from django.db import models as djm
from markdownx.models import MarkdownxField
from markdownx.utils import markdownify

from users.models import User


class NewsTag(djm.Model):
    name = djm.CharField(max_length=32)


class NewsItem(djm.Model):
    title = djm.CharField(max_length=256)
    summary = djm.TextField(max_length=300)
    content = MarkdownxField()
    datetime = djm.DateTimeField()
    edited = djm.BooleanField(default=False)
    edit_note = djm.CharField(null=True, blank=True, default=None, max_length=256)
    edit_datetime = djm.DateTimeField(null=True, blank=True, default=None)
    author = djm.ForeignKey(User, blank=True, null=True, on_delete=djm.SET_NULL, related_name='author')
    edit_author = djm.ForeignKey(User, null=True, blank=True, on_delete=djm.SET_NULL, related_name='edit_author')
    tags = djm.ManyToManyField(NewsTag, blank=True)
    source = djm.URLField(null=True, blank=True, max_length=256)
    cover_img = djm.ImageField(null=True, blank=True, max_length=256)
    generated = djm.BooleanField(default=True)

    def __str__(self):
        return self.title

    class Meta:
        unique_together = ['title', 'datetime']
        ordering = ['datetime', 'title']

    @property
    def content_html(self):
        return markdownify(self.content)

    def gen_summary(self):
        content = self.content[:300]
        if len(content) == 300:
            summary = content
        else:
            summary = content.rsplit(' ', 1)[0] + " ..."
        if summary != summary:
            self.summary = summary
            self.save()


class NewsVote(djm.Model):
    UPVOTE = 1
    DOWNVOTE = 2
    AWARD = 3
    CLICKBAIT = 4

    VOTE_TYPE_CHOICES = (
        (UPVOTE, 'upvote'),
        (DOWNVOTE, 'downvote'),
        (AWARD, 'award'),
        (CLICKBAIT, 'clickbait')
    )
    news_item = djm.ForeignKey(NewsItem, on_delete=djm.CASCADE)
    user = djm.ForeignKey(User, null=True, on_delete=djm.SET_NULL)
    vote_type = djm.IntegerField(choices=VOTE_TYPE_CHOICES)
