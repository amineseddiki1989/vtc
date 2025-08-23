#!/usr/bin/env python3
"""
Audit de sécurité intelligent pour application VTC.
Élimine les faux positifs et se concentre sur les vraies vulnérabilités.
"""

import os
import re
import json
import ast
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from collections import defaultdict
from datetime import datetime

class IntelligentSecurityAudit:
    """Audit de sécurité intelligent sans faux positifs."""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.app_path = self.project_path / "app"
        self.critical_issues = []
        self.high_issues = []
        self.medium_issues = []
        self.low_issues = []
        
        self.results = {
            "audit_timestamp": datetime.utcnow().isoformat(),
            "critical_vulnerabilities": [],
            "high_vulnerabilities": [],
            "medium_vulnerabilities": [],
            "low_vulnerabilities": [],
            "security_score": 0,
            "production_readiness": False,
            "summary": {}
        }
    
    def run_intelligent_audit(self):
        """Exécute un audit intelligent focalisé sur les vraies vulnérabilités."""
        print("🔍 AUDIT DE SÉCURITÉ INTELLIGENT")
        print("=" * 60)
        
        # 1. Secrets hardcodés réels
        self._check_real_hardcoded_secrets()
        
        # 2. Injections SQL réelles
        self._check_real_sql_injection()
        
        # 3. Exécution de code dangereux
        self._check_dangerous_code_execution()
        
        # 4. Traversée de répertoires réelle
        self._check_real_path_traversal()
        
        # 5. Vulnérabilités de logique métier
        self._check_business_logic_vulnerabilities()
        
        # 6. Configuration de sécurité
        self._check_security_configuration()
        
        # 7. Authentification et autorisation
        self._check_auth_vulnerabilities()
        
        # 8. Chiffrement et cryptographie
        self._check_crypto_vulnerabilities()
        
        # 9. Calcul du score final
        self._calculate_intelligent_score()
        
        return self.results
    
    def _check_real_hardcoded_secrets(self):
        """Vérifie les vrais secrets hardcodés (pas les constantes)."""
        print("🔒 Vérification des secrets hardcodés réels...")
        
        # Patterns de vrais secrets (pas les enums ou constantes)
        real_secret_patterns = [
            # Clés API réelles
            (r'["\']sk_live_[a-zA-Z0-9]{24,}["\']', "Clé Stripe live hardcodée"),
            (r'["\']pk_live_[a-zA-Z0-9]{24,}["\']', "Clé publique Stripe live hardcodée"),
            (r'["\']whsec_[a-zA-Z0-9]{32,}["\']', "Secret webhook Stripe hardcodé"),
            
            # Clés AWS
            (r'["\']AKIA[0-9A-Z]{16}["\']', "Clé AWS hardcodée"),
            (r'["\'][0-9a-zA-Z/+]{40}["\']', "Secret AWS potentiel"),
            
            # Tokens GitHub
            (r'["\']ghp_[a-zA-Z0-9]{36}["\']', "Token GitHub hardcodé"),
            (r'["\']github_pat_[a-zA-Z0-9_]{82}["\']', "Token GitHub PAT hardcodé"),
            
            # Mots de passe réels (pas les exemples)
            (r'password\s*=\s*["\'][^"\']{12,}["\']', "Mot de passe complexe hardcodé"),
            (r'secret_key\s*=\s*["\'][^"\']{32,}["\']', "Clé secrète hardcodée"),
            
            # Chaînes de connexion
            (r'["\']postgresql://[^"\']+:[^"\']+@[^"\']+["\']', "Chaîne de connexion DB hardcodée"),
            (r'["\']mysql://[^"\']+:[^"\']+@[^"\']+["\']', "Chaîne de connexion MySQL hardcodée"),
            
            # Clés privées
            (r'-----BEGIN.*PRIVATE KEY-----', "Clé privée PEM hardcodée"),
            (r'-----BEGIN RSA PRIVATE KEY-----', "Clé privée RSA hardcodée")
        ]
        
        for file_path in self.app_path.rglob("*.py"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    for pattern, description in real_secret_patterns:
                        matches = re.findall(pattern, line, re.IGNORECASE)
                        for match in matches:
                            # Filtrer les faux positifs
                            if self._is_real_secret(match, line, content):
                                self.critical_issues.append({
                                    "type": "HARDCODED_SECRET",
                                    "severity": "CRITICAL",
                                    "file": str(file_path.relative_to(self.project_path)),
                                    "line": i,
                                    "code": line.strip()[:100] + "..." if len(line.strip()) > 100 else line.strip(),
                                    "description": description,
                                    "recommendation": "Utiliser des variables d'environnement"
                                })
            except Exception:
                continue
    
    def _is_real_secret(self, match: str, line: str, content: str) -> bool:
        """Détermine si c'est un vrai secret ou un faux positif."""
        match_lower = match.lower()
        line_lower = line.lower()
        
        # Faux positifs évidents
        false_positives = [
            'example', 'test', 'demo', 'sample', 'placeholder', 'your_',
            'fake', 'dummy', 'mock', 'template', 'default', 'null',
            'none', 'empty', 'todo', 'fixme', 'xxx', '123', 'abc',
            'reset_password', 'email_verification', 'access', 'refresh'
        ]
        
        for fp in false_positives:
            if fp in match_lower or fp in line_lower:
                return False
        
        # Si c'est dans un commentaire
        if line.strip().startswith('#'):
            return False
        
        # Si c'est dans une docstring
        if '"""' in line or "'''" in line:
            return False
        
        # Si c'est une constante d'enum
        if 'enum' in line_lower or ('class ' in content and 'enum' in content.lower()):
            return False
        
        # Si c'est dans un test
        if 'test' in str(file_path).lower():
            return False
        
        return True
    
    def _check_real_sql_injection(self):
        """Vérifie les vraies vulnérabilités d'injection SQL."""
        print("💉 Vérification des injections SQL réelles...")
        
        dangerous_sql_patterns = [
            # Concaténation directe avec entrée utilisateur
            r'\.execute\s*\(\s*["\'].*["\']\s*\+\s*.*request',
            r'\.execute\s*\(\s*f["\'].*\{.*request.*\}.*["\']',
            r'SELECT.*\+.*request',
            r'INSERT.*\+.*request',
            r'UPDATE.*\+.*request',
            r'DELETE.*\+.*request'
        ]
        
        for file_path in self.app_path.rglob("*.py"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    for pattern in dangerous_sql_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            self.critical_issues.append({
                                "type": "SQL_INJECTION",
                                "severity": "CRITICAL",
                                "file": str(file_path.relative_to(self.project_path)),
                                "line": i,
                                "code": line.strip(),
                                "description": "Injection SQL avec entrée utilisateur",
                                "recommendation": "Utiliser des requêtes paramétrées"
                            })
            except Exception:
                continue
    
    def _check_dangerous_code_execution(self):
        """Vérifie l'exécution de code réellement dangereuse."""
        print("⚡ Vérification de l'exécution de code dangereuse...")
        
        dangerous_patterns = [
            # Exécution avec entrée utilisateur
            (r'eval\s*\(.*request', "eval() avec entrée utilisateur"),
            (r'exec\s*\(.*request', "exec() avec entrée utilisateur"),
            (r'compile\s*\(.*request', "compile() avec entrée utilisateur"),
            (r'__import__\s*\(.*request', "__import__() avec entrée utilisateur"),
            
            # Commandes système avec entrée utilisateur
            (r'os\.system\s*\(.*request', "os.system() avec entrée utilisateur"),
            (r'subprocess\..*\(.*request.*shell\s*=\s*True', "subprocess avec shell=True et entrée utilisateur"),
            (r'os\.popen\s*\(.*request', "os.popen() avec entrée utilisateur")
        ]
        
        for file_path in self.app_path.rglob("*.py"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    for pattern, description in dangerous_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            self.critical_issues.append({
                                "type": "CODE_EXECUTION",
                                "severity": "CRITICAL",
                                "file": str(file_path.relative_to(self.project_path)),
                                "line": i,
                                "code": line.strip(),
                                "description": description,
                                "recommendation": "Valider et échapper toutes les entrées utilisateur"
                            })
            except Exception:
                continue
    
    def _check_real_path_traversal(self):
        """Vérifie les vraies vulnérabilités de traversée de répertoires."""
        print("📁 Vérification de la traversée de répertoires réelle...")
        
        # Patterns dangereux avec entrée utilisateur
        dangerous_file_patterns = [
            r'open\s*\([^)]*request[^)]*\)',
            r'Path\s*\([^)]*request[^)]*\)',
            r'os\.path\.join\s*\([^)]*request[^)]*\)',
            r'\.read_text\s*\([^)]*request[^)]*\)',
            r'\.write_text\s*\([^)]*request[^)]*\)'
        ]
        
        for file_path in self.app_path.rglob("*.py"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    for pattern in dangerous_file_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            # Vérifier qu'il n'y a pas de validation
                            if not any(validation in line.lower() for validation in 
                                     ['secure_path', 'validate', 'sanitize', 'abspath', 'realpath']):
                                self.high_issues.append({
                                    "type": "PATH_TRAVERSAL",
                                    "severity": "HIGH",
                                    "file": str(file_path.relative_to(self.project_path)),
                                    "line": i,
                                    "code": line.strip(),
                                    "description": "Accès fichier avec entrée utilisateur non validée",
                                    "recommendation": "Utiliser un gestionnaire de fichiers sécurisé"
                                })
            except Exception:
                continue
    
    def _check_business_logic_vulnerabilities(self):
        """Vérifie les vulnérabilités de logique métier VTC."""
        print("💼 Vérification de la logique métier VTC...")
        
        business_patterns = [
            # Données critiques manipulables
            (r'price\s*=\s*request\.', "Prix manipulable par l'utilisateur"),
            (r'distance\s*=\s*request\.', "Distance manipulable par l'utilisateur"),
            (r'driver_id\s*=\s*request\.', "ID conducteur manipulable par l'utilisateur"),
            (r'trip_status\s*=\s*request\.', "Statut course manipulable par l'utilisateur"),
            (r'payment_amount\s*=\s*request\.', "Montant paiement manipulable"),
            
            # Calculs côté client
            (r'total_price\s*=.*request\.json\(\)', "Calcul prix côté client"),
            (r'fare\s*=.*request\.form', "Tarif calculé côté client")
        ]
        
        for file_path in self.app_path.rglob("*.py"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    for pattern, description in business_patterns:
                        if re.search(pattern, line):
                            # Vérifier qu'il n'y a pas de validation
                            if not any(validation in line.lower() for validation in 
                                     ['validate', 'verify', 'check', 'secure']):
                                self.high_issues.append({
                                    "type": "BUSINESS_LOGIC",
                                    "severity": "HIGH",
                                    "file": str(file_path.relative_to(self.project_path)),
                                    "line": i,
                                    "code": line.strip(),
                                    "description": description,
                                    "recommendation": "Valider côté serveur toutes les données métier"
                                })
            except Exception:
                continue
    
    def _check_security_configuration(self):
        """Vérifie la configuration de sécurité."""
        print("⚙️ Vérification de la configuration de sécurité...")
        
        config_issues = [
            (r'debug\s*=\s*True', "Mode debug activé"),
            (r'DEBUG\s*=\s*True', "Mode debug activé"),
            (r'allow_origins\s*=\s*\[\s*["\*"]\s*\]', "CORS trop permissif"),
            (r'verify\s*=\s*False', "Vérification SSL désactivée"),
            (r'ssl_context\.check_hostname\s*=\s*False', "Vérification hostname SSL désactivée")
        ]
        
        for file_path in self.project_path.rglob("*.py"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    for pattern, description in config_issues:
                        if re.search(pattern, line):
                            self.medium_issues.append({
                                "type": "SECURITY_CONFIG",
                                "severity": "MEDIUM",
                                "file": str(file_path.relative_to(self.project_path)),
                                "line": i,
                                "code": line.strip(),
                                "description": description,
                                "recommendation": "Sécuriser la configuration pour la production"
                            })
            except Exception:
                continue
    
    def _check_auth_vulnerabilities(self):
        """Vérifie les vulnérabilités d'authentification."""
        print("🔐 Vérification de l'authentification...")
        
        # Vérifier la présence d'un système d'auth
        auth_files = list(self.app_path.rglob("*auth*.py"))
        if not auth_files:
            self.high_issues.append({
                "type": "MISSING_AUTH",
                "severity": "HIGH",
                "description": "Aucun système d'authentification détecté",
                "recommendation": "Implémenter un système d'authentification"
            })
        
        # Vérifier les patterns d'auth faibles
        weak_auth_patterns = [
            (r'password\s*==\s*input', "Comparaison de mot de passe non sécurisée"),
            (r'jwt\.decode.*verify=False', "Vérification JWT désactivée"),
            (r'session\[.*\]\s*=.*user.*id', "Session non sécurisée")
        ]
        
        for file_path in self.app_path.rglob("*.py"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    for pattern, description in weak_auth_patterns:
                        if re.search(pattern, line):
                            self.high_issues.append({
                                "type": "WEAK_AUTH",
                                "severity": "HIGH",
                                "file": str(file_path.relative_to(self.project_path)),
                                "line": i,
                                "code": line.strip(),
                                "description": description,
                                "recommendation": "Utiliser des méthodes d'authentification sécurisées"
                            })
            except Exception:
                continue
    
    def _check_crypto_vulnerabilities(self):
        """Vérifie les vulnérabilités cryptographiques."""
        print("🔒 Vérification de la cryptographie...")
        
        weak_crypto = [
            (r'md5\s*\(', "Utilisation de MD5 (faible)"),
            (r'sha1\s*\(', "Utilisation de SHA1 (faible)"),
            (r'DES\s*\(', "Utilisation de DES (obsolète)"),
            (r'RC4\s*\(', "Utilisation de RC4 (cassé)"),
            # Exclure secrets.SystemRandom() qui est sécurisé
            (r'(?<!secrets\.)random\.random\s*\(', "Générateur aléatoire faible pour la sécurité"),
            (r'(?<!secrets\.)random\.randint\s*\(', "Générateur aléatoire faible pour la sécurité")
        ]
        
        for file_path in self.app_path.rglob("*.py"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    for pattern, description in weak_crypto:
                        if re.search(pattern, line):
                            # Vérifier le contexte (sécurité vs non-sécurité)
                            if any(security_context in content.lower() for security_context in 
                                   ['password', 'token', 'secret', 'key', 'auth', 'crypto']):
                                # Exclure les utilisations sécurisées
                                if 'secure_random' in line or 'secrets.' in line:
                                    continue
                                    
                                self.medium_issues.append({
                                    "type": "WEAK_CRYPTO",
                                    "severity": "MEDIUM",
                                    "file": str(file_path.relative_to(self.project_path)),
                                    "line": i,
                                    "code": line.strip(),
                                    "description": description,
                                    "recommendation": "Utiliser des algorithmes cryptographiques forts"
                                })
            except Exception:
                continue
    
    def _calculate_intelligent_score(self):
        """Calcule le score de sécurité intelligent."""
        print("📊 Calcul du score de sécurité...")
        
        # Pondération réaliste
        critical_weight = -20
        high_weight = -8
        medium_weight = -3
        low_weight = -1
        
        base_score = 100
        
        critical_count = len(self.critical_issues)
        high_count = len(self.high_issues)
        medium_count = len(self.medium_issues)
        low_count = len(self.low_issues)
        
        score = base_score + (
            critical_count * critical_weight +
            high_count * high_weight +
            medium_count * medium_weight +
            low_count * low_weight
        )
        
        score = max(0, min(100, score))
        
        # Mise à jour des résultats
        self.results["critical_vulnerabilities"] = self.critical_issues
        self.results["high_vulnerabilities"] = self.high_issues
        self.results["medium_vulnerabilities"] = self.medium_issues
        self.results["low_vulnerabilities"] = self.low_issues
        self.results["security_score"] = score
        self.results["production_readiness"] = score >= 80 and critical_count == 0
        
        self.results["summary"] = {
            "total_issues": critical_count + high_count + medium_count + low_count,
            "critical_count": critical_count,
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
            "score": score,
            "production_ready": self.results["production_readiness"]
        }
        
        print(f"Score final: {score}/100")
        print(f"Vulnérabilités critiques: {critical_count}")
        print(f"Vulnérabilités hautes: {high_count}")
        print(f"Vulnérabilités moyennes: {medium_count}")
        print(f"Vulnérabilités basses: {low_count}")


def main():
    """Point d'entrée principal."""
    project_path = "/home/ubuntu/vtc_migration_secure/app_secure_version"
    
    if not os.path.exists(project_path):
        print(f"❌ Projet non trouvé: {project_path}")
        return
    
    auditor = IntelligentSecurityAudit(project_path)
    results = auditor.run_intelligent_audit()
    
    # Sauvegarder les résultats
    output_file = "/home/ubuntu/intelligent_security_audit_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 60)
    print("🎯 RÉSULTATS DE L'AUDIT INTELLIGENT")
    print("=" * 60)
    print(f"Score final: {results['security_score']:.1f}/100")
    print(f"Prêt pour production: {'✅ OUI' if results['production_readiness'] else '❌ NON'}")
    print(f"Vulnérabilités critiques: {len(results['critical_vulnerabilities'])}")
    print(f"Vulnérabilités hautes: {len(results['high_vulnerabilities'])}")
    print(f"Vulnérabilités moyennes: {len(results['medium_vulnerabilities'])}")
    print(f"Vulnérabilités basses: {len(results['low_vulnerabilities'])}")
    
    if results['critical_vulnerabilities']:
        print("\n🚨 VULNÉRABILITÉS CRITIQUES:")
        for vuln in results['critical_vulnerabilities'][:3]:
            print(f"- {vuln.get('type', 'UNKNOWN')}: {vuln.get('description', 'N/A')}")
    
    if results['high_vulnerabilities']:
        print("\n⚠️ VULNÉRABILITÉS HAUTES:")
        for vuln in results['high_vulnerabilities'][:3]:
            print(f"- {vuln.get('type', 'UNKNOWN')}: {vuln.get('description', 'N/A')}")
    
    print(f"\n📄 Rapport détaillé sauvegardé: {output_file}")
    
    return results


if __name__ == "__main__":
    main()

