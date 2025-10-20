from django.contrib import admin
from django.http import HttpResponse
import csv
from .models import User
from .forms import BulkUploadForm
from django.shortcuts import render, redirect
from django.contrib import messages
import pandas as pd
from django.core.exceptions import ValidationError
from io import StringIO

class UserAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'wallet_balance', 'is_expired', 'expired_date', 'created_at']
    list_filter = ['is_expired', 'created_at']
    search_fields = ['name', 'email']
    actions = ['mark_as_expired', 'revert_from_expired']
    
    def mark_as_expired(self, request, queryset):
        for user in queryset:
            if not user.is_expired:
                user.mark_as_expired()
        self.message_user(request, f"Successfully marked {queryset.count()} users as expired")
    mark_as_expired.short_description = "Mark selected users as expired"
    
    def revert_from_expired(self, request, queryset):
        for user in queryset:
            if user.is_expired:
                user.revert_from_expired()
        self.message_user(request, f"Successfully reverted {queryset.count()} users from expired")
    revert_from_expired.short_description = "Revert selected users from expired"
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('bulk-upload/', self.admin_site.admin_view(self.bulk_upload_view), name='users_bulk_upload'),
        ]
        return custom_urls + urls
    
    def bulk_upload_view(self, request):
        if request.method == 'POST':
            form = BulkUploadForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES['csv_file']
                
                try:
                    # Read CSV file
                    df = pd.read_csv(csv_file)
                    required_columns = ['name', 'email', 'wallet_balance']
                    
                    # Validate CSV structure
                    if not all(col in df.columns for col in required_columns):
                        messages.error(request, f"CSV must contain columns: {', '.join(required_columns)}")
                        return render(request, 'users/bulk_upload.html', {'form': form})
                    
                    errors = []
                    success_count = 0
                    processed_data = []
                    
                    # Process each row
                    for index, row in df.iterrows():
                        try:
                            user_data = {
                                'name': str(row['name']).strip(),
                                'email': str(row['email']).strip().lower(),
                                'wallet_balance': float(row['wallet_balance']),
                            }
                            
                            # Validate user data
                            user = User(**user_data)
                            user.full_clean()
                            processed_data.append((index + 2, user_data, None))  # +2 for header and 1-based index
                            success_count += 1
                            
                        except Exception as e:
                            errors.append(f"Row {index + 2}: {str(e)}")
                            processed_data.append((index + 2, dict(row), str(e)))
                    
                    # If no errors, save all users
                    if not errors:
                        for _, user_data, _ in processed_data:
                            User.objects.create(**user_data)
                        messages.success(request, f"Successfully uploaded {success_count} users")
                        return redirect('admin:users_user_changelist')
                    else:
                        # Create error CSV for download
                        error_csv = StringIO()
                        error_writer = csv.writer(error_csv)
                        error_writer.writerow(['row_number', 'name', 'email', 'wallet_balance', 'error'])
                        
                        for row_num, data, error in processed_data:
                            if error:
                                error_writer.writerow([row_num, data.get('name', ''), data.get('email', ''), data.get('wallet_balance', ''), error])
                        
                        request.session['error_csv'] = error_csv.getvalue()
                        messages.error(request, f"Found {len(errors)} errors. Please download the error report and fix the issues.")
                        return render(request, 'users/upload_result.html', {
                            'errors': errors,
                            'success_count': success_count,
                            'total_count': len(df)
                        })
                        
                except Exception as e:
                    messages.error(request, f"Error processing CSV: {str(e)}")
        else:
            form = BulkUploadForm()
        
        return render(request, 'users/bulk_upload.html', {'form': form})

admin.site.register(User, UserAdmin)