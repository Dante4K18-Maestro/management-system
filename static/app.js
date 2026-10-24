(() => {
  const $ = (selector) => document.querySelector(selector);
  const els = {
    rows: $('#student-rows'), search: $('#search'), status: $('#status-filter'),
    course: $('#course-filter'), year: $('#year-filter'), count: $('#record-count'), summary: $('#result-summary'),
    empty: $('#empty-state'), emptyCopy: $('#empty-copy'), form: $('#student-form'),
    dialog: $('#student-dialog'), deleteDialog: $('#delete-dialog'), toast: $('#toast'),
    id: $('#student-id'), error: $('#form-error'), save: $('#save-button'),
  };
  const palette = [
    ['#eaf1ec','#62836b'], ['#f3ece8','#a27764'], ['#ecedf4','#747d9a'],
    ['#f3eee3','#98824d'], ['#eeeaf3','#847097'], ['#e9f0f0','#5b8580'],
  ];
  let students = [];
  let deleteId = null;
  let toastTimer;
  let searchTimer;

  async function request(url, options = {}) {
    let response;
    try {
      response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
    } catch {
      throw new Error('Could not reach the server. Check that StudentHub is running.');
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || 'Something went wrong. Please try again.');
    return data;
  }

  function showToast(message, isError = false) {
    clearTimeout(toastTimer);
    els.toast.textContent = message;
    els.toast.classList.toggle('error-toast', isError);
    els.toast.classList.add('visible');
    toastTimer = setTimeout(() => els.toast.classList.remove('visible'), 2800);
  }

  function makeCell(className, text) {
    const cell = document.createElement('td');
    if (className) cell.className = className;
    if (text !== undefined) cell.textContent = text;
    return cell;
  }

  function studentRow(student, index) {
    const tr = document.createElement('tr');
    const nameCell = makeCell();
    const person = document.createElement('div'); person.className = 'student-cell';
    const initials = `${student.first_name.charAt(0)}${student.last_name.charAt(0)}`.toUpperCase();
    const avatar = document.createElement('span'); avatar.className = 'student-avatar';
    const [background, color] = palette[index % palette.length];
    avatar.style.backgroundColor = background; avatar.style.color = color; avatar.textContent = initials;
    const name = document.createElement('div');
    const fullName = document.createElement('div'); fullName.className = 'student-name';
    fullName.textContent = `${student.first_name} ${student.last_name}`;
    const email = document.createElement('div'); email.className = 'student-email'; email.textContent = student.email;
    name.append(fullName, email); person.append(avatar, name); nameCell.append(person); tr.append(nameCell);

    tr.append(makeCell('student-id', `NS-${String(student.id).padStart(4, '0')}`));
    const course = makeCell();
    const courseName = document.createElement('div'); courseName.className = 'course-name'; courseName.textContent = student.course;
    const year = document.createElement('div'); year.className = 'course-year'; year.textContent = `Year ${student.year}`;
    course.append(courseName, year); tr.append(course);

    const enrolled = new Date(`${student.enrollment_date}T00:00:00`);
    tr.append(makeCell('date-cell', Number.isNaN(enrolled.valueOf()) ? student.enrollment_date : enrolled.toLocaleDateString('en', { day: 'numeric', month: 'short', year: 'numeric' })));
    const status = makeCell(); const pill = document.createElement('span');
    pill.className = `status-pill status-${student.status.toLowerCase().replaceAll(' ', '-')}`;
    pill.textContent = student.status; status.append(pill); tr.append(status);

    const actions = makeCell('row-actions');
    const toggle = document.createElement('button'); toggle.type = 'button'; toggle.className = 'menu-toggle';
    toggle.setAttribute('aria-label', `Actions for ${student.first_name} ${student.last_name}`);
    toggle.setAttribute('aria-haspopup', 'true'); toggle.textContent = '···';
    const menu = document.createElement('div'); menu.className = 'row-menu';
    const edit = document.createElement('button'); edit.type = 'button'; edit.textContent = 'Edit details';
    edit.addEventListener('click', () => openEdit(student));
    const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = 'Remove student'; remove.className = 'delete-action';
    remove.addEventListener('click', () => openDelete(student));
    menu.append(edit, remove);
    toggle.addEventListener('click', (event) => {
      event.stopPropagation();
      const wasOpen = menu.classList.contains('open');
      document.querySelectorAll('.row-menu.open').forEach((item) => item.classList.remove('open'));
      if (!wasOpen) menu.classList.add('open');
    });
    actions.append(toggle, menu); tr.append(actions);
    return tr;
  }

  function syncCourseOptions(courses) {
    const selected = els.course.value;
    els.course.replaceChildren(new Option('All courses', ''));
    const suggestions = $('#course-suggestions'); suggestions.replaceChildren();
    for (const course of courses) {
      els.course.add(new Option(course, course));
      suggestions.append(new Option(course, course));
    }
    els.course.value = courses.includes(selected) ? selected : '';
  }

  async function loadStudents() {
    const params = new URLSearchParams();
    if (els.search.value.trim()) params.set('search', els.search.value.trim());
    if (els.status.value) params.set('status', els.status.value);
    if (els.course.value) params.set('course', els.course.value);
    if (els.year.value) params.set('year', els.year.value);
    try {
      const data = await request(`/api/students?${params}`);
      students = data.students;
      $('#stat-total').textContent = data.stats.total;
      $('#stat-active').textContent = data.stats.active;
      $('#stat-leave').textContent = data.stats.leave_count;
      $('#stat-graduated').textContent = data.stats.graduated;
      $('#nav-count').textContent = data.stats.total;
      els.count.textContent = students.length;
      els.summary.textContent = `Showing ${students.length} of ${data.stats.total} student${data.stats.total === 1 ? '' : 's'}`;
      els.rows.replaceChildren(...students.map(studentRow));
      syncCourseOptions(data.courses);
      const noMatches = data.stats.total > 0;
      els.empty.hidden = students.length > 0;
      els.emptyCopy.textContent = noMatches ? 'Try a different search or filter to find a student.' : 'Start with a name. We’ll take it from there.';
      $('#empty-add').hidden = noMatches;
    } catch (error) {
      showToast(error.message, true);
    }
  }

  function today() { return new Date().toISOString().slice(0, 10); }

  function openAdd() {
    els.form.reset(); els.id.value = ''; els.error.textContent = '';
    els.form.elements.enrollment_date.value = today();
    $('#dialog-eyebrow').textContent = 'ADD TO YOUR ROSTER';
    $('#dialog-title').textContent = 'A new beginning.';
    els.save.innerHTML = 'Add student <span>→</span>';
    els.dialog.showModal(); els.form.elements.first_name.focus();
  }

  function openEdit(student) {
    els.form.reset(); els.id.value = student.id; els.error.textContent = '';
    for (const field of els.form.elements) {
      if (field.name && Object.hasOwn(student, field.name)) field.value = student[field.name];
    }
    $('#dialog-eyebrow').textContent = 'UPDATE STUDENT RECORD';
    $('#dialog-title').textContent = 'A little update.';
    els.save.innerHTML = 'Save changes <span>→</span>';
    els.dialog.showModal(); els.form.elements.first_name.focus();
  }

  function openDelete(student) {
    document.querySelectorAll('.row-menu.open').forEach((item) => item.classList.remove('open'));
    deleteId = student.id;
    $('#delete-dialog h2').textContent = `Remove ${student.first_name}?`;
    els.deleteDialog.showModal();
  }

  els.form.addEventListener('submit', async (event) => {
    event.preventDefault(); els.error.textContent = '';
    const submit = els.save; submit.disabled = true;
    const data = Object.fromEntries(new FormData(els.form).entries());
    try {
      const editing = Boolean(els.id.value);
      await request(editing ? `/api/students/${els.id.value}` : '/api/students', {
        method: editing ? 'PATCH' : 'POST', body: JSON.stringify(data),
      });
      els.dialog.close(); await loadStudents(); showToast(editing ? 'Student record updated.' : 'New student added to the roster.');
    } catch (error) {
      els.error.textContent = error.message;
    } finally { submit.disabled = false; }
  });

  $('#confirm-delete').addEventListener('click', async () => {
    const button = $('#confirm-delete'); button.disabled = true;
    try {
      await request(`/api/students/${deleteId}`, { method: 'DELETE' });
      els.deleteDialog.close(); await loadStudents(); showToast('Student removed from the roster.');
    } catch (error) { showToast(error.message, true); }
    finally { button.disabled = false; }
  });

  function csvCell(value) {
    const safe = String(value ?? '').replace(/^[\s\u0000-\u001f]*[=+@-]/, "'$&");
    return `"${safe.replaceAll('"', '""')}"`;
  }

  $('#export-csv').addEventListener('click', () => {
    if (!students.length) return showToast('There are no student records to export.');
    const columns = ['Student ID', 'First name', 'Last name', 'Email', 'Phone', 'Course', 'Year', 'Status', 'Enrollment date'];
    const lines = [columns, ...students.map((s) => [`NS-${String(s.id).padStart(4, '0')}`, s.first_name, s.last_name, s.email, s.phone, s.course, s.year, s.status, s.enrollment_date])]
      .map((row) => row.map(csvCell).join(',')).join('\r\n');
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob(['\uFEFF', lines], { type: 'text/csv;charset=utf-8' }));
    link.download = 'northstar-students.csv'; link.click(); URL.revokeObjectURL(link.href);
    showToast(`Exported ${students.length} student record${students.length === 1 ? '' : 's'}.`);
  });

  $('#add-student').addEventListener('click', openAdd);
  $('#empty-add').addEventListener('click', openAdd);
  $('#close-dialog').addEventListener('click', () => els.dialog.close());
  $('#cancel-dialog').addEventListener('click', () => els.dialog.close());
  $('#keep-student').addEventListener('click', () => els.deleteDialog.close());
  els.search.addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadStudents, 200); });
  els.status.addEventListener('change', loadStudents);
  els.course.addEventListener('change', loadStudents);
  els.year.addEventListener('change', loadStudents);
  document.addEventListener('click', () => document.querySelectorAll('.row-menu.open').forEach((item) => item.classList.remove('open')));

  loadStudents();
})();
