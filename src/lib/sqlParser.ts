// src/lib/sqlParser.ts
import { Table, Column, Relationship, DatabaseSchema } from '@/types/Table'

export class SQLParser {
  private tables: Map<string, Table> = new Map()
  private relationships: Relationship[] = []

  parseSQLScript(sqlScript: string): DatabaseSchema {
    // Limpar dados anteriores
    this.tables.clear()
    this.relationships = []

    // Dividir o script em statements
    const statements = this.splitStatements(sqlScript)

    // Processar cada statement
    for (const statement of statements) {
      this.processStatement(statement.trim())
    }

    // Detectar relacionamentos por convenção
    this.detectRelationshipsByConvention()

    return {
      tables: Array.from(this.tables.values()),
      relationships: this.relationships
    }
  }

  private splitStatements(sql: string): string[] {
    // Remove comentários
    sql = sql.replace(/--.*$/gm, '')
    sql = sql.replace(/\/\*[\s\S]*?\*\//g, '')
    
    // Divide por ponto e vírgula
    const statements = sql.split(';').filter(stmt => stmt.trim().length > 0)
    return statements
  }

  private processStatement(statement: string): void {
    const upperStatement = statement.toUpperCase()
    
    if (upperStatement.startsWith('CREATE TABLE')) {
      this.parseCreateTable(statement)
    }
  }

  private parseCreateTable(statement: string): void {
    // Regex para extrair nome da tabela
    const tableNameMatch = statement.match(/CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)/i)
    if (!tableNameMatch) return

    const tableName = tableNameMatch[1]

    // Extrair conteúdo entre parênteses
    const contentMatch = statement.match(/\(([\s\S]*)\)/)
    if (!contentMatch) return

    const content = contentMatch[1]
    
    // Dividir por vírgulas (considerando parênteses aninhados)
    const columnDefinitions = this.splitColumnDefinitions(content)
    
    const columns: Column[] = []
    const primaryKeys: string[] = []
    
    for (const definition of columnDefinitions) {
      const trimmed = definition.trim()
      
      if (trimmed.toUpperCase().startsWith('PRIMARY KEY')) {
        // Extrair colunas da primary key
        const pkMatch = trimmed.match(/PRIMARY\s+KEY\s*\(([^)]+)\)/i)
        if (pkMatch) {
          const pkColumns = pkMatch[1].split(',').map(col => col.trim().replace(/["`]/g, ''))
          primaryKeys.push(...pkColumns)
        }
      } else if (trimmed.toUpperCase().startsWith('FOREIGN KEY')) {
        // Processar foreign key
        this.parseForeignKey(trimmed, tableName)
      } else if (trimmed.length > 0 && !trimmed.toUpperCase().startsWith('CONSTRAINT')) {
        // Processar coluna normal
        const column = this.parseColumnDefinition(trimmed)
        if (column) {
          columns.push(column)
        }
      }
    }

    // Marcar primary keys
    for (const column of columns) {
      if (primaryKeys.includes(column.name)) {
        column.primaryKey = true
      }
    }

    this.tables.set(tableName, {
      name: tableName,
      columns
    })
  }

  private splitColumnDefinitions(content: string): string[] {
    const definitions: string[] = []
    let current = ''
    let parenDepth = 0
    
    for (let i = 0; i < content.length; i++) {
      const char = content[i]
      
      if (char === '(') {
        parenDepth++
      } else if (char === ')') {
        parenDepth--
      } else if (char === ',' && parenDepth === 0) {
        definitions.push(current.trim())
        current = ''
        continue
      }
      
      current += char
    }
    
    if (current.trim()) {
      definitions.push(current.trim())
    }
    
    return definitions
  }

  private parseColumnDefinition(definition: string): Column | null {
    // Regex para extrair informações da coluna
    const parts = definition.trim().split(/\s+/)
    if (parts.length < 2) return null

    const name = parts[0].replace(/["`]/g, '')
    const type = parts[1]
    
    const upperDef = definition.toUpperCase()
    
    return {
      name,
      type,
      nullable: !upperDef.includes('NOT NULL'),
      primaryKey: upperDef.includes('PRIMARY KEY')
    }
  }

  private parseForeignKey(definition: string, tableName: string): void {
    // FOREIGN KEY (column) REFERENCES table(column)
    const fkMatch = definition.match(/FOREIGN\s+KEY\s*\(([^)]+)\)\s+REFERENCES\s+(\w+)\s*\(([^)]+)\)/i)
    
    if (fkMatch) {
      const sourceColumn = fkMatch[1].trim().replace(/["`]/g, '')
      const targetTable = fkMatch[2].trim()
      const targetColumn = fkMatch[3].trim().replace(/["`]/g, '')
      
      // Atualizar a coluna com informação de FK
      const table = this.tables.get(tableName)
      if (table) {
        const column = table.columns.find(col => col.name === sourceColumn)
        if (column) {
          column.foreignKey = {
            table: targetTable,
            column: targetColumn
          }
        }
      }
      
      // Adicionar relacionamento
      this.relationships.push({
        from: { table: tableName, column: sourceColumn },
        to: { table: targetTable, column: targetColumn },
        type: 'MANY_TO_ONE'
      })
    }
  }

  private detectRelationshipsByConvention(): void {
    const tableNames = Array.from(this.tables.keys())
    
    for (const [tableName, table] of this.tables) {
      for (const column of table.columns) {
        // Pular se já tem foreign key explícita
        if (column.foreignKey) continue
        
        // Detectar apenas por convenções específicas de FK
        const possibleReferences = this.findPossibleReferences(column.name, tableNames, tableName)
        
        for (const ref of possibleReferences) {
          // Verificar se já existe esse relacionamento
          const relationshipExists = this.relationships.some(rel => 
            rel.from.table === tableName && 
            rel.from.column === column.name &&
            rel.to.table === ref.tableName &&
            rel.to.column === ref.columnName
          )
          
          if (!relationshipExists) {
            const refTable = this.tables.get(ref.tableName)
            if (refTable) {
              const refColumn = refTable.columns.find(col => col.name === ref.columnName)
              if (refColumn && this.areColumnsCompatible(column, refColumn)) {
                // Adicionar relacionamento detectado por convenção
                this.relationships.push({
                  from: { table: tableName, column: column.name },
                  to: { table: ref.tableName, column: ref.columnName },
                  type: 'MANY_TO_ONE'
                })
              }
            }
          }
        }
      }
    }
  }

  private findPossibleReferences(columnName: string, tableNames: string[], currentTable: string): Array<{tableName: string, columnName: string}> {
    const references: Array<{tableName: string, columnName: string}> = []
    const lowerColumnName = columnName.toLowerCase()
    
    // Apenas detectar padrões específicos de foreign key
    for (const tableName of tableNames) {
      // Não referenciar a própria tabela
      if (tableName === currentTable) continue
      
      const lowerTableName = tableName.toLowerCase()
      
      // Padrão: usuario_id -> usuarios.id
      if (lowerColumnName.endsWith('_id')) {
        const prefix = lowerColumnName.slice(0, -3)
        if (lowerTableName === prefix || lowerTableName === prefix + 's' || lowerTableName === prefix.slice(0, -1)) {
          // Verificar se a tabela tem uma coluna 'id'
          const targetTable = this.tables.get(tableName)
          if (targetTable && targetTable.columns.some(col => col.name.toLowerCase() === 'id')) {
            references.push({ tableName, columnName: 'id' })
          }
        }
      }
      
      // Padrão: post_id -> posts.id  
      if (lowerColumnName.includes('_id')) {
        const parts = lowerColumnName.split('_')
        if (parts.length === 2 && parts[1] === 'id') {
          const prefix = parts[0]
          if (lowerTableName === prefix || lowerTableName === prefix + 's') {
            const targetTable = this.tables.get(tableName)
            if (targetTable && targetTable.columns.some(col => col.name.toLowerCase() === 'id')) {
              references.push({ tableName, columnName: 'id' })
            }
          }
        }
      }
    }
    
    return references
  }

  private areColumnsCompatible(col1: Column, col2: Column): boolean {
    // Simplificada: verifica se os tipos são compatíveis
    const type1 = col1.type.toLowerCase().replace(/\([^)]*\)/g, '')
    const type2 = col2.type.toLowerCase().replace(/\([^)]*\)/g, '')
    
    const integerTypes = ['int', 'integer', 'bigint', 'smallint', 'serial', 'bigserial']
    const stringTypes = ['varchar', 'char', 'text', 'string']
    
    if (integerTypes.includes(type1) && integerTypes.includes(type2)) return true
    if (stringTypes.includes(type1) && stringTypes.includes(type2)) return true
    if (type1 === type2) return true
    
    return false
  }
}