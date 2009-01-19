#encoding=utf-8
import re, calendar, time
from datetime import datetime, date, timedelta

from genshi.builder import tag

from trac.core import *
from trac.web import IRequestHandler
from trac.web.chrome import INavigationContributor, ITemplateProvider
from trac.util.datefmt import to_datetime, parse_date, format_date

class TicketCalendarPlugin(Component):
    implements(INavigationContributor, IRequestHandler, ITemplateProvider)

    # INavigationContributor methods
    def get_active_navigation_item(self, req):
        return 'ticketcalendar'

    def get_navigation_items(self, req):
        if req.perm.has_permission('TICKET_VIEW'):
            yield ('mainnav', 'ticketcalendar',tag.a(u'カレンダー', href=req.href.ticketcalendar()))

    # IRequestHandler methods
    def match_request(self, req):
        return re.match(r'/ticketcalendar(?:_trac)?(?:/.*)?$', req.path_info)

    def calendarRange(self, y, m):
        w,mdays = calendar.monthrange(y,m)
        w = (w + 1) % 7
        firstDay = date(y,m,1)-timedelta(days=w)

        lastDay = date(y,m,mdays)
        w = (lastDay.weekday()+1)%7
        lastDay = lastDay + timedelta(days=(6-w))
        return firstDay, lastDay

    def process_request(self, req):
        ymonth = req.args.get('month')
        yyear = req.args.get('year')
        show_my_ticket = req.args.get('show_my_ticket')
        selected_milestone = req.args.get('selected_milestone')
        cday = date.today()
        if not (not ymonth or not yyear):
            cday = date(int(yyear),int(ymonth),1)

        # cal next month
        nmonth = cday.replace(day=1).__add__(timedelta(days=32)).replace(day=1)

        # cal previous month
        pmonth = cday.replace(day=1).__add__(timedelta(days=-1)).replace(day=1)
        first,last = self.calendarRange(cday.year, cday.month)
        # process ticket
        db = self.env.get_db_cnx()
        cursor = db.cursor();
        my_ticket_sql = ""
        self.log.debug("myticket")
        self.log.debug(show_my_ticket)
        if show_my_ticket=="on":
            my_ticket_sql = "AND owner = '" + req.authname + "'"
        selected_milestone_sql = ""
        if selected_milestone != None and selected_milestone != "":
            selected_milestone_sql = "AND milestone = '" + selected_milestone  + "'"

        sql = ("SELECT id, type, summary, owner, description, status, a.value, c.value from ticket t "
                    "JOIN ticket_custom a ON a.ticket = t.id AND a.name = 'due_assign' "
                    "JOIN ticket_custom c ON c.ticket = t.id AND c.name = 'due_close' "
                    "WHERE ((a.value > '%s' AND a.value < '%s' ) "
                    "OR (c.value > '%s' AND c.value < '%s')) %s %s" %
                    (format_date(parse_date(first.isoformat())),
                        format_date(parse_date(last.isoformat())),
                        format_date(parse_date(first.isoformat())),
                        format_date(parse_date(last.isoformat())),
                        my_ticket_sql,
                        selected_milestone_sql))

        self.log.debug(sql)
        cursor.execute(sql)
        tickets=[]
        for id, type, summary, owner, description, status, due_assign, due_close in cursor:
            due_assign_date = None
            due_close_date = None
            try:
                due_assign_date = parse_date(due_assign).date()
            except ( TracError, ValueError, TypeError):
                pass
            try:
                due_close_date = parse_date(due_close).date()
            except ( TracError, ValueError, TypeError):
                pass
            ticket = {'id':id, 'type':type, 'summary':summary, 'owner':owner, 'description': description, 'status':status, 'due_assign':due_assign_date, 'due_close':due_close_date}
            tickets.append(ticket)

        # get roadmap
        sql = ("SELECT name, due, completed, description from MILESTONE")
        self.log.debug(sql)
        cursor.execute(sql)

        milestones = [{}]
        for name, due, completed, description in cursor:
            if due!=0:
                due_date = to_datetime(due, req.tz).date()
                milestone = {'name':name, 'due':due_date, 'completed':completed != 0,'description':description}
                milestones.append(milestone)

        data = {'current':cday, 'prev':pmonth, 'next':nmonth, 'first':first, 'last':last, 'tickets':tickets, 'milestones':milestones,
                'show_my_ticket': show_my_ticket, 'selected_milestone': selected_milestone}

        return 'calendar.html', data, None

    def get_templates_dirs(self):
        from pkg_resources import resource_filename
        return [resource_filename(__name__, 'templates')]

    def get_htdocs_dirs(self):
        from pkg_resources import resource_filename
        return [('tc', resource_filename(__name__, 'htdocs'))]
