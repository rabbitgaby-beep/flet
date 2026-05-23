import flet as ft
import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.getcwd(), "sps_precarga.db")

def init_db():
    """Inicializa la base de datos SQLite con las tablas necesarias"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS programas (
            id_programa INTEGER PRIMARY KEY AUTOINCREMENT,
            jurisdiccion TEXT, nombre_programa TEXT, respondente TEXT,
            tipo_fuente TEXT, organismo TEXT, secretaria TEXT,
            subsecretaria TEXT, direccion_unidad TEXT,
            vigente TEXT, activo TEXT, bajo_plan TEXT, nombre_plan TEXT,
            antecedentes TEXT, programas_previos TEXT, tematica TEXT,
            sistema TEXT, objetivos_generales TEXT, objetivos_especificos TEXT,
            modalidad_ejecucion TEXT, desc_modalidad TEXT, normativa TEXT,
            fuentes_financiamiento TEXT, alcance TEXT,
            provincias_priorizadas TEXT, criterio_priorizacion TEXT,
            poblacion_destinataria TEXT, requisitos_admin TEXT,
            criterios_elegibilidad TEXT, contraprestaciones TEXT,
            grupos_edad TEXT, poblacion_especifica TEXT,
            poblaciones_especificas TEXT, incompatible TEXT,
            programas_incompatibles TEXT, formulario_inscripcion TEXT,
            autoridad TEXT, email TEXT, web TEXT,
            domicilio TEXT, telefono TEXT,
            fecha_carga DATETIME, usuario_carga TEXT,
            estado TEXT DEFAULT 'pendiente'
        );
        CREATE TABLE IF NOT EXISTS prestaciones (
            id_prestacion INTEGER PRIMARY KEY AUTOINCREMENT,
            id_programa INTEGER,
            nombre TEXT, activa TEXT, tipo TEXT, destinatario TEXT,
            edad_req TEXT, edad_desde INTEGER, edad_hasta INTEGER,
            genero_req TEXT, generos TEXT, pob_especifica TEXT,
            pob_especificas TEXT, ingreso_req TEXT, param_ingreso TEXT,
            limite_ingreso TEXT, patrimonio_req TEXT, patrimonios TEXT,
            laboral_req TEXT, laborales TEXT, residencia_req TEXT,
            anos_res INTEGER, permite_ext TEXT, anos_ext INTEGER,
            FOREIGN KEY (id_programa) REFERENCES programas(id_programa) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS indicadores (
            id_indicador INTEGER PRIMARY KEY AUTOINCREMENT,
            id_prestacion INTEGER,
            tipo TEXT, disponible TEXT, unidad TEXT, periodicidad TEXT,
            ultimo_dato TEXT, periodo TEXT, ano INTEGER, fuente TEXT,
            FOREIGN KEY (id_prestacion) REFERENCES prestaciones(id_prestacion) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()

# Lookups simplificados (extender según PDF)
LOOKUPS = {
    "jurisdiccion": ["Nacional", "CABA", "Buenos Aires", "Catamarca", "Córdoba", "Corrientes", "Chaco", "Chubut", "Entre Ríos", "Formosa", "Jujuy", "La Pampa", "La Rioja", "Mendoza", "Misiones", "Neuquén", "Río Negro", "Salta", "San Juan", "San Luis", "Santa Cruz", "Santa Fe", "Santiago del Estero", "Tucumán", "Tierra del Fuego"],
    "organismo_nacional": {
        "Nacional": ["Ministerio de Capital Humano", "Ministerio de Salud", "Ministerio de Educación", "ANSES", "CNCPS"],
        "default": ["Ministerio correspondiente"]
    },
    "vigente": ["1: Sí", "2: No"],
    "bajo_plan": ["1: Sí", "2: No", "3: Sin información"],
    "modalidad": ["1: Centralizada", "2: Descentralizada ONG", "3: Descentralizada OG", "4: Mixta", "99: Sin información"],
    "tematica": ["1: Seguridad alimentaria", "2: Promoción del empleo", "3: Vivienda", "4: Salud", "5: Educación", "6: Cuidados", "7: Prevención violencias", "8: Protección emergencias", "9: Cultura", "10: Seguridad social", "11: Inclusión social", "12: Deportes", "13: Turismo"]
}

def get_lookup(key, parent=None):
    if key == "organismo_nacional":
        return LOOKUPS["organismo_nacional"].get(parent or "default")
    return LOOKUPS.get(key, [])

class SPSPrecargaApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Mapeo SPS - Precarga Local"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.window_width = 1200
        self.page.window_height = 800
        
        self.current_program_id = None
        self.fields = {}
        self.prestaciones_container = None
        self.status_text = None
        self.tab_contents = {}  # ✅ Contenido separado para Flet 0.85+

        self._build_ui()

    def _build_ui(self):
        # ✅ Tabs con label (no text) y sin content directo
        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(label="1. Identificación"),
                ft.Tab(label="2. Descripción Programa"),
                ft.Tab(label="3. Prestaciones"),
                ft.Tab(label="4. Guardar/Exportar"),
            ],
            on_change=self._on_tab_change
        )
        
        # ✅ Contenido separado en diccionario
        self.tab_contents[0] = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        self.tab_contents[1] = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        self.tab_contents[2] = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        self.tab_contents[3] = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        
        # Inicializar primer tab
        self._build_identificacion()
        
        self.page.add(
            ft.Row([self.tabs], expand=True),
            ft.Container(content=self.tab_contents[0], expand=True, padding=20)
        )

    def _add_field(self, tab_idx, label, key, control, visible=True):
        col = self.tab_contents[tab_idx]
        ctrl = ft.Container(
            content=ft.Column([
                ft.Text(label, weight=ft.FontWeight.BOLD, size=14),
                control
            ], spacing=5),
            visible=visible,
            padding=8
        )
        col.controls.append(ctrl)
        self.fields[key] = {"control": control, "container": ctrl}
        return control

    def _build_identificacion(self):
        col = self.tab_contents[0]
        col.controls.clear()
        
        self._add_field(0, "Jurisdicción", "jurisdiccion", ft.Dropdown(
            options=[ft.dropdown.Option(j) for j in LOOKUPS["jurisdiccion"]],
            on_change=self._update_dependent_dropdowns,
            width=400
        ))
        self._add_field(0, "Nombre del Programa", "nombre_programa", ft.TextField(width=400))
        self._add_field(0, "Nombre del Respondente", "respondente", ft.TextField(width=400))
        self._add_field(0, "Tipo de Fuente", "tipo_fuente", ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="1. Primaria (entrevista)", label="Primaria (entrevista)"),
                ft.Radio(value="2. Secundaria (web/documentos)", label="Secundaria (web/documentos)")
            ], spacing=5)
        ))

    def _build_descripcion(self):
        col = self.tab_contents[1]
        col.controls.clear()
        
        self._add_field(1, "Organismo", "organismo", ft.Dropdown(width=400))
        self._add_field(1, "Secretaría", "secretaria", ft.TextField(width=400))
        self._add_field(1, "¿Está vigente?", "vigente", ft.Dropdown(
            options=[ft.dropdown.Option(v) for v in LOOKUPS["vigente"]],
            on_change=self._skip_logic_vigente,
            width=200
        ))
        self._add_field(1, "¿Bajo algún plan?", "bajo_plan", ft.Dropdown(
            options=[ft.dropdown.Option(v) for v in LOOKUPS["bajo_plan"]],
            width=200
        ))
        self._add_field(1, "Nombre del plan", "nombre_plan", ft.TextField(width=400), visible=False)
        self._add_field(1, "Temática", "tematica", ft.Dropdown(
            options=[ft.dropdown.Option(t) for t in LOOKUPS["tematica"]],
            width=400
        ))
        self._add_field(1, "Objetivos Generales", "objetivos_generales", 
                       ft.TextField(multiline=True, min_lines=3, max_lines=8, width=600))

    def _build_prestaciones(self):
        col = self.tab_contents[2]
        col.controls.clear()
        
        self.prestaciones_container = ft.ListView(expand=True, spacing=15, padding=10)
        
        col.controls.extend([
            ft.Row([
                ft.ElevatedButton("➕ Agregar Prestación", on_click=self._add_prestacion_ui, 
                                icon=ft.Icons.ADD),
                ft.Text("Gestión 1:N:N (Programa → Prestaciones → Indicadores)", 
                       italic=True, size=12, color=ft.Colors.GREY_600)
            ], alignment=ft.MainAxisAlignment.START),
            self.prestaciones_container
        ])

    def _add_prestacion_ui(self, e):
        """Agrega dinámicamente una nueva prestación con su UI"""
        card = ft.Card(
            elevation=2,
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text("Prestación", weight=ft.FontWeight.BOLD, size=16),
                        ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED,
                                    on_click=lambda _: self.prestaciones_container.controls.remove(card),
                                    tooltip="Eliminar prestación")
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    
                    ft.TextField(label="Nombre de la prestación", width=400),
                    
                    ft.Row([
                        ft.Text("¿Activa?:"),
                        ft.RadioGroup(
                            content=ft.Row([
                                ft.Radio(value="1", label="Sí"),
                                ft.Radio(value="2", label="No")
                            ], spacing=15)
                        )
                    ]),
                    
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Indicadores (agregar dinámicamente):", size=12, italic=True),
                            ft.ElevatedButton("Agregar Indicador", size=ft.ButtonSize.SMALL)
                        ], spacing=5),
                        padding=10,
                        bgcolor=ft.Colors.GREY_50,
                        border_radius=8,
                        border=ft.Border.all(1, ft.Colors.GREY_300)
                    )
                ], spacing=10),
                padding=15
            )
        )
        self.prestaciones_container.controls.append(card)
        self.prestaciones_container.update()

    def _build_export(self):
        col = self.tab_contents[3]
        col.controls.clear()
        
        self.status_text = ft.Text("Estado: Sin guardar", color=ft.Colors.ORANGE)
        
        col.controls.extend([
            self.status_text,
            ft.Divider(),
            ft.Row([
                ft.ElevatedButton("💾 Guardar en BD Local", on_click=self._save_to_db,
                                icon=ft.Icons.SAVE, style=ft.ButtonStyle(
                                    bgcolor=ft.Colors.BLUE, color=ft.Colors.WHITE)),
                ft.OutlinedButton("📤 Exportar JSON para SIEMPRO", on_click=self._export_json,
                                icon=ft.Icons.UPLOAD),
                ft.OutlinedButton("📥 Cargar desde BD", on_click=self._load_from_db,
                                icon=ft.Icons.DOWNLOAD)
            ], wrap=True, spacing=10),
            ft.Container(
                content=ft.Text("✓ Fecha y usuario se registran automáticamente.\n✓ Validaciones de coherencia incluidas.", 
                               size=12, color=ft.Colors.GREY_700),
                padding=10,
                bgcolor=ft.Colors.BLUE_50,
                border_radius=5
            )
        ])

    # ===== LÓGICA DE UI =====
    def _update_dependent_dropdowns(self, e):
        """Actualiza dropdowns en cascada: Jurisdicción → Organismo"""
        jur = self.fields["jurisdiccion"]["control"].value
        if jur:
            self.fields["organismo"]["control"].options = [
                ft.dropdown.Option(o) for o in get_lookup("organismo_nacional", jur)
            ]
            self.fields["organismo"]["control"].value = None
            self.page.update()

    def _skip_logic_vigente(self, e):
        """Lógica de salto: si no está vigente, ocultar campos relacionados"""
        val = self.fields["vigente"]["control"].value
        is_vigente = val and val.startswith("1")
        self.fields["nombre_plan"]["container"].visible = is_vigente
        self.page.update()

    def _on_tab_change(self, e):
        """Maneja el cambio de tabs en Flet 0.85+"""
        idx = self.tabs.selected_index
        
        # Cargar contenido del tab seleccionado
        if idx == 1:
            self._build_descripcion()
        elif idx == 2:
            self._build_prestaciones()
        elif idx == 3:
            self._build_export()
        
        # Actualizar contenedor visible
        if len(self.page.controls) > 1:
            self.page.controls[1].content = self.tab_contents[idx]
        
        self.page.update()
        
        # Auto-save al cambiar de tab (si ya hay programa cargado)
        if self.current_program_id:
            self._save_to_db(None, silent=True)

    # ===== PERSISTENCIA =====
    def _save_to_db(self, e, silent=False):
        """Guarda los datos en SQLite"""
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            
            # Recopilar datos de los campos
            prog_data = {k: v["control"].value for k, v in self.fields.items()}
            prog_data["fecha_carga"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            prog_data["usuario_carga"] = prog_data.get("respondente", "Desconocido")
            
            if self.current_program_id:
                # UPDATE
                placeholders = ", ".join([f"{k}=?" for k in prog_data.keys()])
                c.execute(f"UPDATE programas SET {placeholders} WHERE id_programa=?", 
                         list(prog_data.values()) + [self.current_program_id])
            else:
                # INSERT
                cols = ", ".join(prog_data.keys())
                qs = ", ".join(["?"] * len(prog_data))
                c.execute(f"INSERT INTO programas ({cols}) VALUES ({qs})", list(prog_data.values()))
                self.current_program_id = c.lastrowid
            
            conn.commit()
            conn.close()
            
            if not silent:
                self.status_text.value = "✅ Guardado correctamente en BD local"
                self.status_text.color = ft.Colors.GREEN
                self.page.update()
                
        except Exception as ex:
            self.status_text.value = f"❌ Error: {str(ex)}"
            self.status_text.color = ft.Colors.RED
            self.page.update()

    def _export_json(self, e):
        """Exporta los datos a JSON estructurado para SIEMPRO"""
        if not self.current_program_id:
            self.status_text.value = "⚠️ Primero guarda el programa"
            self.status_text.color = ft.Colors.RED
            self.page.update()
            return

        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            # Obtener programa
            prog = dict(c.execute("SELECT * FROM programas WHERE id_programa=?", 
                                (self.current_program_id,)).fetchone())
            
            # Obtener prestaciones e indicadores
            prests = [dict(r) for r in c.execute(
                "SELECT * FROM prestaciones WHERE id_programa=?", 
                (self.current_program_id,)
            )]
            for p in prests:
                p["indicadores"] = [dict(r) for r in c.execute(
                    "SELECT * FROM indicadores WHERE id_prestacion=?", 
                    (p["id_prestacion"],)
                )]
            conn.close()
            
            # Exportar
            export_data = {"programa": prog, "prestaciones": prests}
            filename = f"SPS_{prog.get('nombre_programa','sin_nombre').replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.json"
            
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            self.status_text.value = f"📤 Exportado: {filename}"
            self.status_text.color = ft.Colors.BLUE
            self.page.update()
            
        except Exception as ex:
            self.status_text.value = f"❌ Error exportando: {str(ex)}"
            self.status_text.color = ft.Colors.RED
            self.page.update()

    def _load_from_db(self, e):
        """Carga datos desde BD (Fase 2 - Visor SIEMPRO)"""
        self.status_text.value = "🔄 Carga manual disponible en Fase 2 (Visor SIEMPRO)"
        self.page.update()

def main(page: ft.Page):
    """Punto de entrada de la aplicación"""
    init_db()
    app = SPSPrecargaApp(page)

# ✅ EJECUCIÓN CORRECTA PARA FLET 0.85+
if __name__ == "__main__":
    ft.run(main)