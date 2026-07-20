from flask_wtf import FlaskForm
from wtforms import PasswordField, SubmitField
from wtforms.validators import DataRequired


class AdminLoginForm(FlaskForm):
    password = PasswordField(
        "Administrator password",
        validators=[DataRequired(message="Enter the administrator password.")],
        render_kw={
            "autocomplete": "current-password",
            "autocapitalize": "none",
            "spellcheck": "false",
        },
    )
    submit = SubmitField("Open Admin Portal")
