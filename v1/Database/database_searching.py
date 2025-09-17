from storage_utils import *


users = get_user_data_from_json()

user_email_dict = {}
for entry_value in users:
    email = entry_value['email']
    user_email_dict[email] = user_email_dict.get(email, 0) + 1

emails_with_more_than_two = [email for email,
                             count in user_email_dict.items() if count > 2]
print("Emails with more than 2 occurrences:", len(emails_with_more_than_two))
print(emails_with_more_than_two[0])

user_number_dict = {}
for entry_value in users:
    number = entry_value.get('number')
    if number:
        user_number_dict[number] = user_number_dict.get(number, 0) + 1

numbers_with_more_than_one = [number for number,
                              count in user_number_dict.items() if count > 1]
print("Numbers with more than 1 occurrence:", numbers_with_more_than_one)
