from django import forms

class BulkUploadForm(forms.Form):
    csv_file = forms.FileField(
        label='CSV File',
        help_text='Upload a CSV file with columns: name, email, wallet_balance'
    )