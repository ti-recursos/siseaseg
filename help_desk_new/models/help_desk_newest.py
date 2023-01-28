from odoo import api, models, fields

# falta imprimir preguntas y respuuestas almacenadas segun el tipo de consulta seleccionada   default y dominio
class  Ctype_frecuent_questions(models.Model): 
    _inherit = 'helpdesk.ticket'

    consulta_type = fields.Many2one ('consult.type' , string='Tipo de evento') #nombre cambiable 

class Tiposdeconsult(models.Model):
    _name = 'consult.type'
    _description = 'Tipos de eventos' #nombre cambiable
    name= fields.Char(string='Tipo de evento') #nombre cambiable
    relacionauno= fields.One2many('questioins.answers' , 'relacionados' ,string='Relacion questions')

class Questions(models.Model):
    _name = 'questioins.answers'
    _description = 'Preguntas y respuestas de Eventos'
  
    relacionados= fields.Many2one('consult.type' , string='Relacion Questions')
    preguntas = fields.Text(string='Preguntas')
    respuestas = fields.Text(string='Respuestas')
    name= fields.Many2one(string='Relación', related='relacionados', readonly="1")
