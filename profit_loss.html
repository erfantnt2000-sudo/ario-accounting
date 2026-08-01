{% extends "base.html" %}
{% block title %}اشخاص | حسابداری آریو{% endblock %}
{% block page_title %}<strong>اشخاص (مشتری / تأمین‌کننده)</strong>{% endblock %}
{% block content %}
<div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h2 style="margin:0;">فهرست اشخاص</h2>
        <a href="{{ url_for('party_add') }}" class="btn btn-primary">+ شخص جدید</a>
    </div>
    <table>
        <thead>
            <tr>
                <th>کد</th>
                <th>نام</th>
                <th>نوع</th>
                <th>تلفن</th>
                <th>عملیات</th>
            </tr>
        </thead>
        <tbody>
            {% for p in parties %}
            <tr>
                <td>{{ p.code or '—' }}</td>
                <td>{{ p.name }}</td>
                <td>
                    {% if p.party_type == 'customer' %}مشتری
                    {% elif p.party_type == 'supplier' %}تأمین‌کننده
                    {% else %}هر دو{% endif %}
                </td>
                <td class="text-left">{{ p.phone or '—' }}</td>
                <td><a href="{{ url_for('party_edit', pid=p.id) }}" class="btn btn-sm btn-secondary">ویرایش</a></td>
            </tr>
            {% else %}
            <tr><td colspan="5" style="text-align:center;">شخصی ثبت نشده.</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
