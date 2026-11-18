from frappe.model.document import Document

from softsystem97.technician_exams.rules import track_for, validate_question


class SS97TechnicianExamQuestion(Document):
    def validate(self):
        track_for(self.track)
        validate_question(self.prompt, self.options_json,
                          self.correct_option, self.category or "")
