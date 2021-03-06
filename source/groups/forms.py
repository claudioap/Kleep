from dal import autocomplete
from django import forms as djf
from django.core.exceptions import ValidationError
from markdownx.fields import MarkdownxFormField

from groups import models as m
from chat import models as chat
from supernova.fields import NativeSplitDateTimeField
from supernova.widgets import SliderInput, NativeTimeInput, NativeDateInput
from groups import permissions


class GroupSettingsForm(djf.ModelForm):
    def __init__(self, *args, **kwargs):
        super(GroupSettingsForm, self).__init__(*args, **kwargs)
        self.fields['default_role'].queryset = kwargs['instance'].roles

    class Meta:
        model = m.Group
        fields = ('description', 'image', 'icon', 'outsiders_openness', 'default_role', 'place')
        widgets = {
            'place': autocomplete.ModelSelect2(url='college:place_ac')
        }


# TODO audit the usage of this
class RoleForm(djf.ModelForm):
    class Meta:
        model = m.Role
        fields = '__all__'
        exclude = ('group',)
        widgets = {
            'is_admin': SliderInput(),
            'can_modify_roles': SliderInput(),
            'can_assign_roles': SliderInput(),
            'can_announce': SliderInput(),
            'can_read_conversations': SliderInput(),
            'can_write_conversations': SliderInput(),
            'can_read_internal_conversations': SliderInput(),
            'can_write_internal_conversations': SliderInput(),
            'can_read_internal_documents': SliderInput(),
            'can_write_internal_documents': SliderInput(),
            'can_write_public_documents': SliderInput(),
            'can_change_schedule': SliderInput()}


# TODO audit the usage of this
class MembershipForm(djf.ModelForm):
    class Meta:
        model = m.Membership
        fields = ('member', 'role', 'group')
        widgets = {
            'member': autocomplete.ModelSelect2(url='users:nickname_ac'),
            'role': autocomplete.ModelSelect2(url='groups:group_role_ac', forward=['group'])}


class MembershipRequestForm(djf.ModelForm):
    # TODO add group field and freeze it
    class Meta:
        model = m.MembershipRequest
        fields = ('message',)


class BaseGroupMembershipFormSet(djf.BaseInlineFormSet):
    def __init__(self, changing_user, *args, **kwargs):
        super(BaseGroupMembershipFormSet, self).__init__(*args, **kwargs)
        self.current_user = changing_user

    def clean(self):
        super().clean()
        current_permissions = permissions.get_user_group_permissions(self.current_user, self.instance)
        for form in self.forms:
            if not form.has_changed():
                continue
            if form.instance:
                old_role_permissions = permissions.roles_combined((form.instance.role,))
                if not permissions.can_handle_permissions(current_permissions, old_role_permissions):
                    raise djf.ValidationError("O cargo anterior tinha mais permissões do que o utilizador atual.")

                new_role = form.cleaned_data.get('role')
                new_role_permissions = permissions.roles_combined((new_role,))
                if not permissions.can_handle_permissions(current_permissions, new_role_permissions):
                    raise djf.ValidationError("O cargo definido tem mais permissões que o utilizador atual.")

        for form in self.deleted_forms:
            old_role_permissions = permissions.roles_combined((form.instance.role,))
            if not permissions.can_handle_permissions(current_permissions, old_role_permissions):
                raise djf.ValidationError("Não pode remover membros com mais do que as suas permissões.")


# TODO figure how to limit a form field queryset through this
# to prevent attacks such as asking for a role from other group
GroupMembershipFormSet = djf.inlineformset_factory(
    m.Group,
    m.Membership,
    extra=3,
    form=MembershipForm,
    formset=BaseGroupMembershipFormSet)


class AnnounceForm(djf.ModelForm):
    class Meta:
        model = m.Announcement
        fields = ('title', 'content')


class ScheduleOnceForm(djf.ModelForm):
    datetime = NativeSplitDateTimeField()

    class Meta:
        model = m.ScheduleOnce
        fields = ('title', 'datetime', 'duration')
        widgets = {'duration': djf.NumberInput(attrs={'min': 0, 'max': 24 * 60, 'size': 3})}


GroupScheduleOnceFormset = djf.inlineformset_factory(m.Group, m.ScheduleOnce, extra=1, form=ScheduleOnceForm)


class SchedulePeriodicForm(djf.ModelForm):
    class Meta:
        model = m.SchedulePeriodic
        fields = ('title', 'weekday', 'time', 'duration', 'start_date', 'end_date')
        widgets = {
            'time': NativeTimeInput(),
            'duration': djf.NumberInput(attrs={'min': 0, 'max': 24 * 60, 'size': 3}),
            'start_date': NativeDateInput(),
            'end_date': NativeDateInput()
        }

    def clean(self):
        start_date = self.cleaned_data.get("start_date")
        end_date = self.cleaned_data.get("end_date")
        weekday = self.cleaned_data.get("weekday")
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError("O evento termina antes de começar.")

            # Days before the first event occurrence
            uncounted = weekday - start_date.weekday() \
                if start_date.weekday() <= weekday \
                else weekday + 7 - start_date.weekday()
            uncounted += end_date.weekday() - weekday \
                if weekday <= end_date.weekday() \
                else end_date.weekday() - weekday + 7

            if (end_date - start_date).days - uncounted < 7:
                raise ValidationError("Este evento não tem periodicidade, deveria de ser pontual.")


GroupSchedulePeriodicFormset = djf.inlineformset_factory(m.Group, m.SchedulePeriodic, extra=1,
                                                         form=SchedulePeriodicForm)


class GroupExternalConversationCreation(djf.ModelForm):
    message = MarkdownxFormField()

    class Meta:
        model = chat.GroupExternalConversation
        fields = ('title', 'public')
