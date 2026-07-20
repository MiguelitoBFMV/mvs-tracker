from django import forms

from games.models import LibraryEntry


class LibraryEntryOwnerForm(forms.ModelForm):
    class Meta:
        model = LibraryEntry
        fields = (
            "has_platinum",
            "main_story_hours_override",
            "notes",
        )
        labels = {
            "has_platinum": "Platinum Unlocked",
            "main_story_hours_override": (
                "Manual Main Story Duration"
            ),
            "notes": "Library Notes",
        }
        widgets = {
            "has_platinum": forms.CheckboxInput(
                attrs={
                    "class": "detail-owner-checkbox",
                }
            ),
            "main_story_hours_override": (
                forms.NumberInput(
                    attrs={
                        "class": "detail-owner-control",
                        "min": "0.1",
                        "step": "0.1",
                        "placeholder": "Hours",
                    }
                )
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": (
                        "detail-owner-control "
                        "detail-owner-textarea"
                    ),
                    "rows": 4,
                    "placeholder": (
                        "Personal context, priorities or notes..."
                    ),
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        manual_hours = cleaned_data.get(
            "main_story_hours_override"
        )

        if (
            self.instance.status
            == LibraryEntry.Status.MULTIPLAYER
            and manual_hours is not None
        ):
            self.add_error(
                "main_story_hours_override",
                (
                    "Persistent multiplayer games do not use "
                    "a main-story duration."
                ),
            )

        return cleaned_data