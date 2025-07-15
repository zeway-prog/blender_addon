#!/usr/bin/env python3
"""
Script de test pour vérifier que l'addon FaceIt fonctionne correctement
après les corrections apportées pour Blender 4.4
"""

def test_imports():
    """Test que tous les imports fonctionnent correctement"""
    print("=== TEST DES IMPORTS ===")
    
    try:
        # Test de l'import SoundSequence/SoundStrip 
        from mocap.mocap_scene_properties import shapes_action_poll
        print("✅ Import mocap_scene_properties OK")
    except Exception as e:
        print(f"❌ Erreur import mocap_scene_properties: {e}")
    
    try:
        # Test des imports des opérateurs
        from animate.animate_operators import FACEIT_OT_MirrorCopy, FACEIT_OT_ExpressionInfo
        print("✅ Import animate_operators OK")
    except Exception as e:
        print(f"❌ Erreur import animate_operators: {e}")
    
    try:
        # Test des imports des panneaux
        from panels.expressions_panel import FACEIT_PT_ExpressionsUI
        print("✅ Import expressions_panel OK")
    except Exception as e:
        print(f"❌ Erreur import expressions_panel: {e}")

def test_operator_properties():
    """Test que les opérateurs ont les bonnes propriétés"""
    print("\n=== TEST DES PROPRIÉTÉS D'OPÉRATEURS ===")
    
    try:
        from animate.animate_operators import FACEIT_OT_MirrorCopy
        
        # Vérifier que l'opérateur a la propriété expression_to_mirror
        if hasattr(FACEIT_OT_MirrorCopy, 'expression_to_mirror'):
            print("✅ FACEIT_OT_MirrorCopy.expression_to_mirror existe")
        else:
            print("❌ FACEIT_OT_MirrorCopy.expression_to_mirror manquante")
            
        # Vérifier les méthodes
        if hasattr(FACEIT_OT_MirrorCopy, 'execute'):
            print("✅ FACEIT_OT_MirrorCopy.execute() existe")
        else:
            print("❌ FACEIT_OT_MirrorCopy.execute() manquante")
            
    except Exception as e:
        print(f"❌ Erreur test MirrorCopy: {e}")

if __name__ == "__main__":
    print("Test de l'addon FaceIt après corrections Blender 4.4")
    print("=" * 50)
    
    test_imports()
    test_operator_properties()
    
    print("\n=== RÉSUMÉ ===")
    print("Si tous les tests affichent ✅, l'addon devrait fonctionner correctement dans Blender 4.4")
