{% extends "base.html" %}
{% block title %}تراز آزمایشی | حسابداری آریو{% endblock %}
{% block page_title %}<strong>تراز آزمایشی</strong>{% endblock %}
{% block content %}
<div class="card">
    <h2>تراز آزمایشی حساب‌ها</h2>
    <table>
        <thead>
            <tr>
                <th>کد</th>
                <th>نام حساب</th>
                <th>جمع بدهکار</th>
                <th>جمع بستانکار</th>
                <th>مانده بدهکار</th>
                <th>مانده بستانکار</th>
            </tr>
        </thead>
        <tbody>
            {% for r in rows %}
            <tr>
                <td class="text-left">{{ r.code }}</td>
                <td>{{ r.name }}</td>
                <td class="text-left">{{ "{:,.0f}".format(r.debit) if r.debit else '' }}</td>
                <td class="text-left">{{ "{:,.0f}".format(r.credit) if r.credit else '' }}</td>
                <td class="text-left">{{ "{:,.0f}".format(r.bal_debit) if r.bal_debit else '' }}</td>
                <td class="text-left">{{ "{:,.0f}".format(r.bal_credit) if r.bal_credit else '' }}</td>
            </tr>
            {% endfor %}
        </tbody>
        <tfoot>
            <tr style="font-weight:bold;background:#eaf2f8;">
                <td colspan="4">جمع مانده‌ها</td>
                <td class="text-left">{{ "{:,.0f}".format(total_d) }}</td>
                <td class="text-left">{{ "{:,.0f}".format(total_c) }}</td>
            </tr>
        </tfoot>
    </table>
</div>
{% endblock %}
