export const roles = ["Administrator", "Coordinator", "Approver", "Faculty", "Student"];

export const roleDescription = {
  Administrator: "Manage user accounts, roles and access.",
  Coordinator: "Prepare academic data and generate schedules.",
  Approver: "Review schedules before publishing.",
  Faculty: "View your published schedule and manage your availability.",
  Student: "View your batch’s published class and exam schedules.",
};

export const fieldNames = {
  username: "Username", full_name: "Full name", email: "Email", role: "Role",
  current_password: "Current password", password: "Password",
  instructor_id: "Instructor", batch_id: "Batch", department_id: "Department",
  "department.code": "Department code", "department.name": "Department name",
  program_code: "Programme code", batch_year: "Year", section: "Section",
  strength: "Student count", max_daily_hours: "Maximum daily hours",
  max_weekly_hours: "Maximum weekly hours",
};

export function fieldName(name) {
  return fieldNames[name] || fieldNames[name.replace(/^(instructor|batch)\./, "")] || name;
}

