"""
Modern Design System - Black, Orange, White Theme

Professional color palette and component styles for the DFS Lineup Optimizer.
Bold sports aesthetic with high contrast and energy.
"""

# ============================================================================
# COLOR PALETTE - Black, Orange, White Theme
# ============================================================================

COLORS = {
    # Primary Colors
    'black': '#000000',
    'pure_black': '#0a0a0a',
    'dark_gray': '#1a1a1a',
    'medium_gray': '#2a2a2a',
    'light_gray': '#3a3a3a',
    
    # Orange Accent (Energy, Action, Success)
    'orange_bright': '#ff6b35',    # Primary CTA
    'orange_deep': '#ff5722',      # Hover states
    'orange_light': '#ff8a65',     # Highlights
    'orange_glow': '#ff6b35',      # Glow effects
    
    # White/Light
    'white': '#ffffff',
    'off_white': '#f5f5f5',
    'light_gray_text': '#e0e0e0',
    'medium_gray_text': '#b0b0b0',
    'dark_gray_text': '#707070',
    
    # Semantic Colors
    'success': '#4caf50',          # Green for success
    'warning': '#ffa726',          # Amber for warnings
    'danger': '#ef5350',           # Red for errors
    'info': '#29b6f6',             # Blue for info
    
    # Borders & Dividers
    'border_light': 'rgba(255, 255, 255, 0.1)',
    'border_medium': 'rgba(255, 255, 255, 0.2)',
    'border_orange': 'rgba(255, 107, 53, 0.3)',
}

# ============================================================================
# TYPOGRAPHY
# ============================================================================

FONTS = {
    'primary': "-apple-system, BlinkMacSystemFont, 'Inter', 'SF Pro Display', 'Segoe UI', Roboto, system-ui, sans-serif",
    'mono': "'SF Mono', 'Monaco', 'Cascadia Code', 'Roboto Mono', Consolas, monospace"
}

FONT_SIZES = {
    'hero': '2.5rem',      # 40px
    'h1': '2rem',          # 32px
    'h2': '1.5rem',        # 24px
    'h3': '1.25rem',       # 20px
    'body': '1rem',        # 16px
    'small': '0.875rem',   # 14px
    'tiny': '0.75rem',     # 12px
}

FONT_WEIGHTS = {
    'regular': '400',
    'medium': '500',
    'semibold': '600',
    'bold': '700',
}

# ============================================================================
# SPACING SCALE
# ============================================================================

SPACING = {
    'xs': '0.25rem',   # 4px
    'sm': '0.5rem',    # 8px
    'md': '1rem',      # 16px
    'lg': '1.5rem',    # 24px
    'xl': '2rem',      # 32px
    '2xl': '3rem',     # 48px
    '3xl': '4rem',     # 64px
}

# ============================================================================
# GLOBAL BASE STYLES
# ============================================================================

def get_base_styles() -> str:
    """Get global base styles for the app."""
    return f"""
    <style>
    /* ========== ROOT & GLOBALS ========== */
    :root {{
        --primary-black: {COLORS['black']};
        --pure-black: {COLORS['pure_black']};
        --dark-gray: {COLORS['dark_gray']};
        --orange-bright: {COLORS['orange_bright']};
        --orange-deep: {COLORS['orange_deep']};
        --white: {COLORS['white']};
        --spacing-md: {SPACING['md']};
    }}
    
    /* App Background */
    .stApp {{
        background: linear-gradient(180deg, {COLORS['pure_black']} 0%, {COLORS['black']} 100%);
        color: {COLORS['white']};
        font-family: {FONTS['primary']};
    }}
    
    /* Main content area */
    .main .block-container {{
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }}
    
    /* Remove default Streamlit padding on mobile */
    @media (max-width: 768px) {{
        .main .block-container {{
            padding-left: 1rem;
            padding-right: 1rem;
        }}
    }}
    
    /* ========== TYPOGRAPHY ========== */
    h1, h2, h3, h4, h5, h6 {{
        color: {COLORS['white']};
        font-weight: {FONT_WEIGHTS['bold']};
        letter-spacing: -0.02em;
    }}
    
    p, span, div {{
        color: {COLORS['light_gray_text']};
    }}
    
    /* ========== BUTTONS ========== */
    /* Primary Button - Orange */
    .stButton > button[kind="primary"],
    button[kind="primary"] {{
        background: linear-gradient(135deg, {COLORS['orange_bright']} 0%, {COLORS['orange_deep']} 100%);
        color: {COLORS['white']};
        border: none;
        border-radius: 12px;
        padding: 0.75rem 2rem;
        font-weight: {FONT_WEIGHTS['semibold']};
        font-size: {FONT_SIZES['body']};
        transition: all 0.3s ease;
        box-shadow: 0 4px 12px rgba(255, 107, 53, 0.3);
        text-transform: none;
        letter-spacing: 0;
    }}
    
    .stButton > button[kind="primary"]:hover,
    button[kind="primary"]:hover {{
        background: linear-gradient(135deg, {COLORS['orange_deep']} 0%, {COLORS['orange_bright']} 100%);
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(255, 107, 53, 0.4);
    }}
    
    /* Secondary Button - White Outline */
    .stButton > button[kind="secondary"],
    button[kind="secondary"] {{
        background: transparent;
        color: {COLORS['white']};
        border: 2px solid {COLORS['border_medium']};
        border-radius: 12px;
        padding: 0.75rem 2rem;
        font-weight: {FONT_WEIGHTS['medium']};
        transition: all 0.3s ease;
    }}
    
    .stButton > button[kind="secondary"]:hover,
    button[kind="secondary"]:hover {{
        border-color: {COLORS['orange_bright']};
        color: {COLORS['orange_bright']};
        background: rgba(255, 107, 53, 0.05);
    }}
    
    /* Default Button */
    .stButton > button {{
        background: {COLORS['medium_gray']};
        color: {COLORS['white']};
        border: 1px solid {COLORS['border_light']};
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: {FONT_WEIGHTS['medium']};
        transition: all 0.2s ease;
    }}
    
    .stButton > button:hover {{
        background: {COLORS['light_gray']};
        border-color: {COLORS['border_medium']};
    }}
    
    /* ========== FILE UPLOADER ========== */
    .stFileUploader {{
        background: {COLORS['dark_gray']};
        border: 2px dashed {COLORS['border_medium']};
        border-radius: 16px;
        padding: 3rem 2rem;
        transition: all 0.3s ease;
    }}
    
    .stFileUploader:hover {{
        border-color: {COLORS['orange_bright']};
        background: {COLORS['medium_gray']};
    }}
    
    .stFileUploader label {{
        color: {COLORS['white']} !important;
        font-size: {FONT_SIZES['body']};
        font-weight: {FONT_WEIGHTS['medium']};
    }}
    
    .stFileUploader small {{
        color: {COLORS['medium_gray_text']};
    }}
    
    /* ========== INPUTS & FORMS ========== */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div > select {{
        background: {COLORS['dark_gray']};
        color: {COLORS['white']};
        border: 1px solid {COLORS['border_light']};
        border-radius: 8px;
        padding: 0.75rem;
    }}
    
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stSelectbox > div > div > select:focus {{
        border-color: {COLORS['orange_bright']};
        box-shadow: 0 0 0 2px rgba(255, 107, 53, 0.2);
    }}
    
    /* ========== SLIDERS ========== */
    .stSlider > div > div > div > div {{
        background: {COLORS['orange_bright']};
    }}
    
    .stSlider > div > div > div {{
        background: {COLORS['medium_gray']};
    }}
    
    /* ========== ALERTS & MESSAGES ========== */
    .stSuccess {{
        background: rgba(76, 175, 80, 0.1);
        border-left: 4px solid {COLORS['success']};
        color: {COLORS['white']};
        border-radius: 8px;
        padding: 1rem;
    }}
    
    .stInfo {{
        background: rgba(41, 182, 246, 0.1);
        border-left: 4px solid {COLORS['info']};
        color: {COLORS['white']};
        border-radius: 8px;
        padding: 1rem;
    }}
    
    .stWarning {{
        background: rgba(255, 167, 38, 0.1);
        border-left: 4px solid {COLORS['warning']};
        color: {COLORS['white']};
        border-radius: 8px;
        padding: 1rem;
    }}
    
    .stError {{
        background: rgba(239, 83, 80, 0.1);
        border-left: 4px solid {COLORS['danger']};
        color: {COLORS['white']};
        border-radius: 8px;
        padding: 1rem;
    }}
    
    /* ========== EXPANDERS ========== */
    .streamlit-expanderHeader {{
        background: {COLORS['dark_gray']};
        border: 1px solid {COLORS['border_light']};
        border-radius: 8px;
        color: {COLORS['white']};
        font-weight: {FONT_WEIGHTS['medium']};
    }}
    
    .streamlit-expanderHeader:hover {{
        border-color: {COLORS['orange_bright']};
        background: {COLORS['medium_gray']};
    }}
    
    .streamlit-expanderContent {{
        background: {COLORS['pure_black']};
        border: 1px solid {COLORS['border_light']};
        border-top: none;
    }}
    
    /* ========== DIVIDERS ========== */
    hr {{
        border-color: {COLORS['border_light']};
        margin: {SPACING['lg']} 0;
    }}
    
    /* ========== SIDEBAR ========== */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, {COLORS['pure_black']} 0%, {COLORS['dark_gray']} 100%);
        border-right: 1px solid {COLORS['border_light']};
    }}
    
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {{
        color: {COLORS['white']};
    }}
    
    /* Sidebar responsive behavior */
    @media (min-width: 768px) {{
        [data-testid="stSidebar"] {{
            min-width: 450px;
            max-width: 450px;
        }}
    }}
    
    @media (max-width: 767px) {{
        [data-testid="stSidebar"] {{
            min-width: auto;
            max-width: 100%;
        }}
        
        [data-testid="stSidebar"][aria-expanded="false"] {{
            display: none;
        }}
    }}
    
    /* ========== CUSTOM UTILITY CLASSES ========== */
    .modern-card {{
        background: linear-gradient(145deg, {COLORS['dark_gray']} 0%, {COLORS['medium_gray']} 100%);
        border: 1px solid {COLORS['border_light']};
        border-radius: 16px;
        padding: {SPACING['xl']};
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        transition: all 0.3s ease;
    }}
    
    .modern-card:hover {{
        border-color: {COLORS['border_orange']};
        box-shadow: 0 8px 16px -2px rgba(0, 0, 0, 0.4);
    }}
    
    .orange-accent {{
        color: {COLORS['orange_bright']};
        font-weight: {FONT_WEIGHTS['semibold']};
    }}
    
    .gradient-text {{
        background: linear-gradient(135deg, {COLORS['white']} 0%, {COLORS['orange_bright']} 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }}
    
    /* ========== ANIMATIONS ========== */
    @keyframes fadeIn {{
        from {{
            opacity: 0;
            transform: translateY(10px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}
    
    @keyframes pulse {{
        0%, 100% {{
            opacity: 1;
        }}
        50% {{
            opacity: 0.5;
        }}
    }}
    
    .fade-in {{
        animation: fadeIn 0.5s ease-out;
    }}
    
    /* ========== LOADING STATES ========== */
    .stSpinner > div {{
        border-top-color: {COLORS['orange_bright']} !important;
    }}
    
    </style>
    """


# ============================================================================
# COMPONENT STYLES
# ============================================================================

def get_hero_section_styles() -> str:
    """Styles for hero/header sections."""
    return f"""
    <style>
    .hero-section {{
        text-align: center;
        padding: {SPACING['2xl']} {SPACING['md']};
        margin-bottom: {SPACING['xl']};
        animation: fadeIn 0.6s ease-out;
    }}
    
    .hero-title {{
        font-size: {FONT_SIZES['hero']};
        font-weight: {FONT_WEIGHTS['bold']};
        color: {COLORS['white']};
        margin-bottom: {SPACING['sm']};
        letter-spacing: -0.03em;
        line-height: 1.2;
    }}
    
    .hero-subtitle {{
        font-size: {FONT_SIZES['h3']};
        color: {COLORS['medium_gray_text']};
        font-weight: {FONT_WEIGHTS['regular']};
        margin-bottom: {SPACING['lg']};
    }}
    
    .hero-accent {{
        color: {COLORS['orange_bright']};
    }}
    
    @media (max-width: 768px) {{
        .hero-title {{
            font-size: {FONT_SIZES['h1']};
        }}
        .hero-subtitle {{
            font-size: {FONT_SIZES['body']};
        }}
    }}
    </style>
    """


def get_upload_zone_styles() -> str:
    """Styles for file upload zones."""
    return f"""
    <style>
    .upload-container {{
        margin: {SPACING['xl']} auto;
        max-width: 800px;
    }}
    
    .upload-zone {{
        background: {COLORS['dark_gray']};
        border: 2px dashed {COLORS['border_medium']};
        border-radius: 16px;
        padding: {SPACING['2xl']};
        text-align: center;
        transition: all 0.3s ease;
        cursor: pointer;
    }}
    
    .upload-zone:hover {{
        border-color: {COLORS['orange_bright']};
        background: {COLORS['medium_gray']};
        box-shadow: 0 0 20px rgba(255, 107, 53, 0.2);
    }}
    
    .upload-icon {{
        font-size: 3rem;
        margin-bottom: {SPACING['md']};
        color: {COLORS['orange_bright']};
    }}
    
    .upload-text {{
        color: {COLORS['white']};
        font-size: {FONT_SIZES['h3']};
        font-weight: {FONT_WEIGHTS['semibold']};
        margin-bottom: {SPACING['sm']};
    }}
    
    .upload-hint {{
        color: {COLORS['medium_gray_text']};
        font-size: {FONT_SIZES['small']};
    }}
    </style>
    """


def get_card_styles() -> str:
    """Styles for card components."""
    return f"""
    <style>
    .stat-card {{
        background: linear-gradient(145deg, {COLORS['dark_gray']} 0%, {COLORS['medium_gray']} 100%);
        border: 1px solid {COLORS['border_light']};
        border-radius: 12px;
        padding: {SPACING['lg']};
        text-align: center;
        transition: all 0.3s ease;
    }}
    
    .stat-card:hover {{
        border-color: {COLORS['orange_bright']};
        transform: translateY(-4px);
        box-shadow: 0 8px 16px rgba(255, 107, 53, 0.2);
    }}
    
    .stat-value {{
        font-size: {FONT_SIZES['h1']};
        font-weight: {FONT_WEIGHTS['bold']};
        color: {COLORS['orange_bright']};
        margin-bottom: {SPACING['xs']};
    }}
    
    .stat-label {{
        font-size: {FONT_SIZES['small']};
        color: {COLORS['medium_gray_text']};
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    
    .info-card {{
        background: {COLORS['dark_gray']};
        border: 1px solid {COLORS['border_light']};
        border-left: 4px solid {COLORS['orange_bright']};
        border-radius: 8px;
        padding: {SPACING['lg']};
        margin: {SPACING['md']} 0;
    }}
    </style>
    """


def get_badge_styles() -> str:
    """Styles for badges and chips."""
    return f"""
    <style>
    .badge {{
        display: inline-block;
        padding: {SPACING['xs']} {SPACING['sm']};
        border-radius: 6px;
        font-size: {FONT_SIZES['tiny']};
        font-weight: {FONT_WEIGHTS['semibold']};
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    
    .badge-orange {{
        background: rgba(255, 107, 53, 0.2);
        color: {COLORS['orange_bright']};
        border: 1px solid {COLORS['orange_bright']};
    }}
    
    .badge-success {{
        background: rgba(76, 175, 80, 0.2);
        color: {COLORS['success']};
        border: 1px solid {COLORS['success']};
    }}
    
    .badge-warning {{
        background: rgba(255, 167, 38, 0.2);
        color: {COLORS['warning']};
        border: 1px solid {COLORS['warning']};
    }}
    
    .badge-white {{
        background: rgba(255, 255, 255, 0.1);
        color: {COLORS['white']};
        border: 1px solid {COLORS['border_medium']};
    }}
    </style>
    """

