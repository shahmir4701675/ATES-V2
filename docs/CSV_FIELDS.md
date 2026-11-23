# CSV field guide

Download a template from **Import CSV** for each entity. Keep the header and save the file in UTF-8. The download contains a synthetic example row. Upload up to 10 MB. Preview shows each rejected line and column before any teaching record is added.

| Type | Fields | Values and references |
| --- | --- | --- |
| Courses | `course_code`, `title`, `department_code`, `credit_hours`, `lecture_hours`, `lab_hours` | Course code is unique. Use the exact code of a saved department. Hours are whole numbers. Lecture and lab hours must total at least one. |
| Instructors | `full_name`, `department_code`, `email`, `max_daily_hours`, `max_weekly_hours` | Use a saved department code and a unique email address. Daily hours must be positive. Weekly hours must be at least daily hours. |
| Rooms | `room_code`, `building`, `capacity`, `room_type` | Room code is unique. Capacity is a positive whole number. Type is Lecture, Lab or Exam Hall. |
| Batches | `department_code`, `program_code`, `batch_year`, `section`, `strength` | Use a saved department code. The programme, four-digit year and section identify the batch. Strength is a positive whole number. |
| Offerings | `term_name`, `course_code`, `program_code`, `batch_year`, `section`, `instructor_email`, `enrolled_count` | Match saved term and teaching records. A course can appear once for the same batch and term. Enrolled count is positive. |
| Enrollments | `term_name`, `course_code`, `program_code`, `batch_year`, `section`, `student_username` | The term, course and batch identify a saved offering. The username must belong to a Student account. |

Import departments and academic terms through the master-data forms before importing their dependents. The same validation applies to browser forms and CSV rows. The wizard checks technical consistency. The department confirms that credits, enrollments, room capacities and availability are accurate.

## Confirm and correct

- Select **Preview import** to see row totals. Correct invalid values in the source CSV and preview it again, or select **Import valid rows** to commit the validated records.
- If you cancel, the teaching tables stay as they were. An updated database can invalidate a preview. Upload the file again to validate its references against current data.
- Use complete rosters for offerings when supplying individual enrollments. Exam scheduling uses the whole batch when an offering has no roster and flags a partially supplied roster for correction.

