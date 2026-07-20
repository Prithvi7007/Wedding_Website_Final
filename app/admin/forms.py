from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, InputRequired, Length, Optional


class AdminLoginForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[Optional(), Length(max=80)],
        render_kw={
            "autocomplete": "username",
            "autocapitalize": "none",
            "spellcheck": "false",
        },
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Enter the administrator password.")],
        render_kw={
            "autocomplete": "current-password",
            "autocapitalize": "none",
            "spellcheck": "false",
        },
    )
    submit = SubmitField("Open Admin Portal")


class InvitationForm(FlaskForm):
    first_name = StringField(
        "Primary first name",
        validators=[
            DataRequired(message="Enter the primary first name."),
            Length(max=200),
        ],
    )
    last_name = StringField(
        "Last name",
        validators=[Optional(), Length(max=200)],
    )
    partner_name = StringField(
        "Partner or household member",
        validators=[Optional(), Length(max=250)],
    )
    display_name = StringField(
        "Invitation display name",
        validators=[
            DataRequired(message="Enter the invitation display name."),
            Length(max=300),
        ],
    )
    represent_side = StringField(
        "Representing side",
        validators=[Optional(), Length(max=120)],
    )
    guest_group = StringField(
        "Guest group",
        validators=[Optional(), Length(max=200)],
    )
    email = StringField(
        "Email",
        validators=[Optional(), Length(max=320)],
    )
    phone = StringField(
        "Phone",
        validators=[Optional(), Length(max=80)],
    )
    message = TextAreaField(
        "General message",
        validators=[Optional(), Length(max=4000)],
    )
    invite_message = TextAreaField(
        "Personal invitation message",
        validators=[Optional(), Length(max=4000)],
    )
    is_active = BooleanField("Invitation is active", default=True)
    submit = SubmitField("Save Invitation")


class AdminRSVPForm(FlaskForm):
    attending = SelectField(
        "Response",
        choices=[
            ("Yes", "Yes — attending"),
            ("No", "No — declined"),
            ("Maybe", "Maybe"),
        ],
        validators=[DataRequired(message="Select an RSVP response.")],
    )
    guest_count = IntegerField(
        "Total attending",
        validators=[InputRequired(message="Enter the guest count.")],
        default=1,
    )
    notes = TextAreaField(
        "Notes",
        validators=[Optional(), Length(max=4000)],
    )
    submit = SubmitField("Save RSVP")


class InvitationChangeRequestForm(FlaskForm):
    first_name = StringField(
        "Primary first name",
        validators=[
            DataRequired(message="Enter the primary first name."),
            Length(max=200),
        ],
    )
    last_name = StringField(
        "Last name",
        validators=[Optional(), Length(max=200)],
    )
    partner_name = StringField(
        "Partner or household member",
        validators=[Optional(), Length(max=250)],
    )
    display_name = StringField(
        "Invitation display name",
        validators=[
            DataRequired(message="Enter the invitation display name."),
            Length(max=300),
        ],
    )
    represent_side = StringField(
        "Representing side",
        validators=[Optional(), Length(max=120)],
    )
    guest_group = StringField(
        "Guest group",
        validators=[Optional(), Length(max=200)],
    )
    email = StringField(
        "Email",
        validators=[Optional(), Length(max=320)],
    )
    phone = StringField(
        "Phone",
        validators=[Optional(), Length(max=80)],
    )
    request_note = TextAreaField(
        "Why should this be changed?",
        validators=[
            DataRequired(message="Explain why this change is needed."),
            Length(max=2000),
        ],
    )
    submit = SubmitField("Submit for Approval")


class RSVPChangeRequestForm(FlaskForm):
    attending = SelectField(
        "Requested response",
        choices=[
            ("Yes", "Yes — attending"),
            ("No", "No — declined"),
            ("Maybe", "Maybe"),
            ("__clear__", "Clear RSVP — no response"),
        ],
        validators=[DataRequired(message="Select an RSVP response.")],
    )
    guest_count = IntegerField(
        "Requested attending",
        validators=[InputRequired(message="Enter the guest count.")],
        default=1,
    )
    max_guests = IntegerField(
        "Requested maximum guests",
        validators=[InputRequired(message="Enter the maximum guests.")],
        default=1,
    )
    notes = TextAreaField(
        "Requested RSVP notes",
        validators=[Optional(), Length(max=4000)],
    )
    request_note = TextAreaField(
        "Why should this be changed?",
        validators=[
            DataRequired(message="Explain why this change is needed."),
            Length(max=2000),
        ],
    )
    submit = SubmitField("Submit for Approval")
