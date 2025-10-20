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
from django.db import transaction

class UserAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'wallet_balance', 'is_expired', 'expired_date', 'created_at']
    list_filter = ['is_expired', 'created_at']
    search_fields = ['name', 'email']
    actions = ['mark_as_expired', 'revert_from_expired']
    
    def mark_as_expired(self, request, queryset):
        success_count = 0
        error_count = 0
        errors = []
        
        for user in queryset:
            if not user.is_expired:
                try:
                    user.mark_as_expired()
                    success_count += 1
                except ValidationError as e:
                    error_count += 1
                    errors.append(f"{user.name}: {str(e)}")
        
        if success_count > 0:
            self.message_user(request, f"Successfully marked {success_count} users as expired")
        if error_count > 0:
            self.message_user(request, f"Failed to mark {error_count} users: {'; '.join(errors)}", level='error')
    
    mark_as_expired.short_description = "Mark selected users as expired"
    
    def revert_from_expired(self, request, queryset):
        success_count = 0
        for user in queryset:
            if user.is_expired:
                user.revert_from_expired()
                success_count += 1
        
        if success_count > 0:
            self.message_user(request, f"Successfully reverted {success_count} users from expired")
        else:
            self.message_user(request, "No expired users were selected", level='warning')
    
    revert_from_expired.short_description = "Revert selected users from expired"
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('bulk-upload/', self.admin_site.admin_view(self.bulk_upload_view), name='users_bulk_upload'),
            path('download-error-csv/', self.admin_site.admin_view(self.download_error_csv), name='users_download_error_csv'),
        ]
        return custom_urls + urls
    
    def download_error_csv(self, request):
        """Download the error CSV from session"""
        error_csv_data = request.session.get('error_csv', None)
        
        if error_csv_data:
            response = HttpResponse(error_csv_data, content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="upload_errors.csv"'
            # Clear the session data after download
            del request.session['error_csv']
            return response
        else:
            messages.error(request, "No error CSV available for download")
            return redirect('admin:users_user_changelist')
    
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
                    
                    # Check if uploading would exceed 10 user limit
                    current_user_count = User.objects.count()
                    new_users_count = len(df)
                    
                    if current_user_count + new_users_count > 10:
                        messages.error(
                            request, 
                            f"Cannot upload {new_users_count} users. Current users: {current_user_count}. "
                            f"Maximum allowed: 10. You can only add {10 - current_user_count} more users."
                        )
                        return render(request, 'users/bulk_upload.html', {'form': form})
                    
                    errors = []
                    success_count = 0
                    processed_data = []
                    
                    # Validate each row first (no database writes)
                    for index, row in df.iterrows():
                        row_num = index + 2  # +2 for header and 1-based indexing
                        try:
                            # Extract and clean data
                            name = str(row['name']).strip()
                            email = str(row['email']).strip().lower()
                            wallet_balance = float(row['wallet_balance'])
                            
                            # Basic validation
                            if not name:
                                raise ValidationError("Name cannot be empty")
                            if not email or '@' not in email:
                                raise ValidationError("Invalid email format")
                            if wallet_balance < 0:
                                raise ValidationError("Wallet balance cannot be negative")
                            
                            # Check for duplicate email in CSV
                            duplicate_in_csv = any(
                                d[1].get('email') == email 
                                for d in processed_data 
                                if d[2] is None
                            )
                            if duplicate_in_csv:
                                raise ValidationError(f"Duplicate email in CSV: {email}")
                            
                            # Check for existing email in database
                            if User.objects.filter(email=email).exists():
                                raise ValidationError(f"Email already exists in database: {email}")
                            
                            user_data = {
                                'name': name,
                                'email': email,
                                'wallet_balance': wallet_balance,
                            }
                            
                            # Validate using model's clean method
                            user = User(**user_data)
                            user.full_clean()
                            
                            processed_data.append((row_num, user_data, None))
                            success_count += 1
                            
                        except (ValidationError, ValueError, KeyError) as e:
                            error_msg = str(e)
                            errors.append(f"Row {row_num}: {error_msg}")
                            processed_data.append((row_num, dict(row), error_msg))
                    
                    # If no errors, save all users in a transaction
                    if not errors:
                        try:
                            with transaction.atomic():
                                for _, user_data, _ in processed_data:
                                    User.objects.create(**user_data)
                                messages.success(request, f"Successfully uploaded {success_count} users")
                                return redirect('admin:users_user_changelist')
                        except Exception as e:
                            messages.error(request, f"Error saving users: {str(e)}")
                            return render(request, 'users/bulk_upload.html', {'form': form})
                    else:
                        # Create error CSV for download
                        error_csv = StringIO()
                        error_writer = csv.writer(error_csv)
                        error_writer.writerow(['row_number', 'name', 'email', 'wallet_balance', 'error'])
                        
                        for row_num, data, error in processed_data:
                            if error:
                                error_writer.writerow([
                                    row_num, 
                                    data.get('name', ''), 
                                    data.get('email', ''), 
                                    data.get('wallet_balance', ''), 
                                    error
                                ])
                        
                        request.session['error_csv'] = error_csv.getvalue()
                        messages.error(
                            request, 
                            f"Found {len(errors)} errors. No data was saved. "
                            f"Please download the error report and fix the issues."
                        )
                        return render(request, 'users/upload_result.html', {
                            'errors': errors,
                            'success_count': 0,
                            'total_count': len(df)
                        })
                        
                except Exception as e:
                    messages.error(request, f"Error processing CSV: {str(e)}")
        else:
            form = BulkUploadForm()
        
        return render(request, 'users/bulk_upload.html', {'form': form})

admin.site.register(User, UserAdmin)