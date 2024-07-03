import requests

API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
headers = {"Authorization": "Bearer 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"}

def query(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    if response:
        return response.json()
    else:
        return False

test = """
What happens in a performance review?

Sources:
employee_handbook.pdf#page=4:  We encourage all employees to be honest and open during the review process, as it is an important opportunity to discuss successes and challenges in the workplace. We aim to provide positive and constructive feedback during performance reviews. This feedback should be used as an opportunity to help employees develop and grow in their roles. Employees will receive a written summary of their performance review which will be discussed during the review session. This written summary will include a rating of the employee's performance, feedback, and goals and objectives for the upcoming year. We understand that performance reviews can be a stressful process. We are committed to making sure that all employees feel supported and empowered during the process. We encourage all employees to reach out to their managers with any questions or concerns they may have. We look forward to conducting performance reviews with all our employees. They are an important part of our commitment to helping our employees grow and develop in their roles.
employee_handbook.pdf#page=4:  Accountability: We take responsibility for our actions and hold ourselves and others accountable for their performance. 8. Community: We are committed to making a positive impact in the communities in which we work and live. Performance Reviews Performance Reviews at Contoso Electronics At Contoso Electronics, we strive to ensure our employees are getting the feedback they need to continue growing and developing in their roles. We understand that performance reviews are a key part of this process and it is important to us that they are conducted in an effective and efficient manner. Performance reviews are conducted annually and are an important part of your career development. During the review, your supervisor will discuss your performance over the past year and provide feedback on areas for improvement. They will also provide you with an opportunity to discuss your goals and objectives for the upcoming year. Performance reviews are a two-way dialogue between managers and employees. We encourage all employees to be honest and open during the review process, as it is an important opportunity to 
role_library.pdf#page=15: appropriate strategies · Foster a culture of engagement, diversity, and inclusion · Lead HR team to provide coaching and guidance to all employees· Manage performance review process and identify areas for improvement · Provide guidance and support to managers on disciplinary action · Maintain employee records and manage payroll QUALIFICATIONS: · Bachelor's degree in Human Resources, Business Administration, or related field . At least 8 years of experience in Human Resources, including at least 5 years in a managerial role · Knowledgeable in Human Resources principles, theories, and practices · Excellent communication and interpersonal skills · Ability to lead, motivate, and develop a high-performing HR team · Strong analytical and problem-solving skills · Ability to handle sensitive information with discretion · Proficient in Microsoft Office Suite Director of Research and Development Job Title: Director of Research and Development, Contoso Electronics Position Summary: The Director of Research and Development is a critical leadership role in Contoso Electronics. This position is responsible for leading the research, development and innovation of our products and services.
"""

output = query({
    "inputs": test,
    "options": {
        "use_cache": False,
        "wait_for_model": True
    },
    "parameters": {
        "temperature" : 1.3,
        "return_full_text": False,
        "top_k": 1,
        "top_p": 0.8,
        "repetition_penalty": 1,
        "max_new_tokens": 150,
        # "max_time": 120,
        # "num_return_sequences": 5,
        # "do_sample": True
    }
})

print(output)
