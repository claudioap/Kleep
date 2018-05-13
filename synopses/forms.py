from dal import autocomplete
from django.core.exceptions import ValidationError
from django.forms import ChoiceField, ModelForm, TextInput
from django import forms

from synopses.models import Area, Subarea, Topic, Section, ClassSection


class AreaForm(ModelForm):
    class Meta:
        model = Area
        fields = '__all__'
        widgets = {
            'area': autocomplete.ModelSelect2(url='synopses:area_ac'),
            'img_url': forms.URLInput()  # TODO URL Field?
        }


class SubareaForm(ModelForm):
    class Meta:
        model = Subarea
        fields = ('area', 'name', 'description', 'img_url')
        widgets = {
            'name': TextInput(),
            'area': autocomplete.ModelSelect2(url='synopses:area_ac'),
            'img_url': forms.URLInput()  # TODO URL Field?
        }


class TopicForm(ModelForm):
    class Meta:
        model = Topic
        fields = ('subarea', 'name')
        widgets = {
            'name': TextInput(),
            'subarea': autocomplete.ModelSelect2(url='synopses:subarea_ac')
        }


class SectionForm(ModelForm):
    after = ChoiceField(label='Após:', required=True)

    class Meta:
        model = Section
        fields = ('name', 'content', 'requirements')
        widgets = {
            'name': TextInput(),
            'requirements': autocomplete.Select2Multiple(url='synopses:section_ac'),
        }

    def clean_after(self):
        after = self.cleaned_data['after']
        try:
            after = int(after)
        except ValueError:
            raise ValidationError("Invalid 'after' value.")
        return after


class ClassSectionForm(ModelForm):
    class Meta:
        model = ClassSection
        fields = '__all__'
        widgets = {
            'corresponding_class': autocomplete.ModelSelect2(url='class_ac'),
            'section': autocomplete.ModelSelect2(url='synopses:section_ac'),
        }
