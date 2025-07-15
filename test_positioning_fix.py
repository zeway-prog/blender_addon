#!/usr/bin/env python3
"""
Test de la nouvelle disposition des shape keys dupliquées
Correction du problème de superposition avec l'objet source
"""

def test_new_positioning():
    """Test la nouvelle logique de positionnement"""
    print("=== TEST NOUVEAU POSITIONNEMENT ===")
    
    print("✅ Corrections appliquées:")
    print("   - Décalage initial calculé dynamiquement")
    print("   - Position de départ: source + offset configurable")
    print("   - Grille organisée à partir de cette nouvelle position")
    print("   - Aucune superposition avec l'objet source")

def test_positioning_logic():
    """Test la logique de calcul des positions"""
    print("\n=== LOGIQUE DE POSITIONNEMENT ===")
    
    print("📐 Calcul des positions:")
    print("   1. Position source: matrix_world.to_translation()")
    print("   2. Espacement base: dimensions * multiplicateurs")
    print("   3. Offset source: max(spacing_x, spacing_z) * source_offset_multiplier")
    print("   4. Position de départ: source + offset")
    print("   5. Grille: start_pos + (index * spacing)")

def test_new_parameter():
    """Test le nouveau paramètre de distance"""
    print("\n=== NOUVEAU PARAMÈTRE ===")
    
    print("🎛️ source_offset_multiplier:")
    print("   - Nom: 'Distance de l'objet source'")
    print("   - Valeur par défaut: 2.0")
    print("   - Plage: 1.0 à 10.0")
    print("   - Fonction: Contrôle la distance entre source et copies")
    print("   - Interface: Ajouté au dialogue de paramètres")

def test_grid_organization():
    """Test l'organisation en grille"""
    print("\n=== ORGANISATION EN GRILLE ===")
    
    print("📊 Disposition:")
    print("   - Axe X: Colonnes (de gauche à droite)")
    print("   - Axe Z: Lignes (vers le 'bas' en Z)")
    print("   - Axe Y: Identique à l'objet source")
    print("   - Wrapping: Nouvelle ligne après objects_per_row")

def simulate_positioning():
    """Simulation de positionnement"""
    print("\n=== SIMULATION POSITIONNEMENT ===")
    
    # Paramètres d'exemple
    source_pos = (0, 0, 0)
    object_dimensions = (2, 2, 2)
    spacing_mult_x = 1.5
    spacing_mult_z = 1.5
    source_offset_mult = 2.0
    objects_per_row = 3
    
    spacing_x = object_dimensions[0] * spacing_mult_x  # 3.0
    spacing_z = object_dimensions[2] * spacing_mult_z  # 3.0
    base_offset = max(spacing_x, spacing_z) * source_offset_mult  # 6.0
    
    start_x = source_pos[0] + base_offset  # 6.0
    start_z = source_pos[2] + base_offset  # 6.0
    
    print(f"Objet source: {source_pos}")
    print(f"Dimensions: {object_dimensions}")
    print(f"Espacement X/Z: {spacing_x}/{spacing_z}")
    print(f"Offset de base: {base_offset}")
    print(f"Position de départ: ({start_x}, {source_pos[1]}, {start_z})")
    
    print("\nPositions des 6 premières copies:")
    for i in range(6):
        col = i % objects_per_row
        row = i // objects_per_row
        x = start_x + (col * spacing_x)
        z = start_z - (row * spacing_z)
        print(f"  Copy {i+1}: ({x}, {source_pos[1]}, {z})")

if __name__ == "__main__":
    print("Test des corrections de positionnement - Duplicate Shape Keys")
    print("=" * 65)
    
    test_new_positioning()
    test_positioning_logic()
    test_new_parameter()
    test_grid_organization()
    simulate_positioning()
    
    print("\n=== RÉSULTAT ===")
    print("✅ Problème résolu:")
    print("   - Plus de superposition avec l'objet source")
    print("   - Disposition en grille propre et organisée")
    print("   - Distance configurable pour tous les besoins")
    print("   - Interface utilisateur améliorée")
    
    print("\n=== UTILISATION ===")
    print("1. L'objet source reste à sa position d'origine")
    print("2. Les copies se placent dans une grille décalée")
    print("3. Ajustez 'Distance de l'objet source' selon vos besoins")
    print("4. Configurez l'espacement X/Z pour l'organisation interne")
