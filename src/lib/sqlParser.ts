// src/lib/sqlParser.ts
import { Table, Column, Relationship, DatabaseSchema } from '@/types/Table'

export class SQLParser {
  private tables: Map<string, Table> = new Map()
  private relationships: Relationship[] = []

  parseSQLScript(sqlScript: string): DatabaseSchema {
    this.tables.clear()
    this.relationships = []

    try {
      // Use robust regex parsing only
      this.fallbackParse(sqlScript)
    } catch (error) {
      console.error('SQL parsing failed:', error)
    }

    this.detectRelationshipsByConvention()

    return {
      tables: Array.from(this.tables.values()),
      relationships: this.relationships
    }
  }

  private fallbackParse(sqlScript: string): void {
    const statements = this.splitStatements(sqlScript)
    
    for (const statement of statements) {
      this.processStatement(statement.trim())
    }
  }

  private splitStatements(sql: string): string[] {
    // Remove comments
    sql = sql.replace(/--.*$/gm, '')
    sql = sql.replace(/\/\*[\s\S]*?\*\//g, '')
    
    return sql.split(';').filter(stmt => stmt.trim().length > 0)
  }

  private processStatement(statement: string): void {
    const upperStatement = statement.toUpperCase()
    
    if (upperStatement.startsWith('CREATE TABLE')) {
      this.parseCreateTable(statement)
    }
  }

  private parseCreateTable(statement: string): void {
    const tableNameMatch = statement.match(/CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)/i)
    if (!tableNameMatch) return

    const tableName = tableNameMatch[1]
    const contentMatch = statement.match(/\(([\s\S]*)\)/)
    if (!contentMatch) return

    const content = contentMatch[1]
    const columnDefinitions = this.splitColumnDefinitions(content)
    
    const columns: Column[] = []
    const primaryKeys: string[] = []
    
    for (const definition of columnDefinitions) {
      const trimmed = definition.trim()
      
      if (trimmed.toUpperCase().startsWith('PRIMARY KEY')) {
        const pkMatch = trimmed.match(/PRIMARY\s+KEY\s*\(([^)]+)\)/i)
        if (pkMatch) {
          const pkColumns = pkMatch[1].split(',').map(col => col.trim().replace(/["`]/g, ''))
          primaryKeys.push(...pkColumns)
        }
      } else if (trimmed.toUpperCase().startsWith('FOREIGN KEY')) {
        this.parseForeignKey(trimmed, tableName)
      } else if (trimmed.length > 0 && !trimmed.toUpperCase().startsWith('CONSTRAINT')) {
        const column = this.parseColumnDefinition(trimmed)
        if (column) columns.push(column)
      }
    }

    // Mark primary keys
    columns.forEach(column => {
      if (primaryKeys.includes(column.name)) {
        column.primaryKey = true
      }
    })

    this.tables.set(tableName, { name: tableName, columns })
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
    const fkMatch = definition.match(/FOREIGN\s+KEY\s*\(([^)]+)\)\s+REFERENCES\s+(\w+)\s*\(([^)]+)\)/i)
    
    if (fkMatch) {
      const sourceColumn = fkMatch[1].trim().replace(/["`]/g, '')
      const targetTable = fkMatch[2].trim()
      const targetColumn = fkMatch[3].trim().replace(/["`]/g, '')
      
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
        if (column.foreignKey) continue
        
        const possibleReferences = this.findPossibleReferences(column.name, tableNames, tableName)
        
        for (const ref of possibleReferences) {
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
    
    for (const tableName of tableNames) {
      if (tableName === currentTable) continue
      
      const lowerTableName = tableName.toLowerCase()
      
      // Pattern: user_id -> users.id
      if (lowerColumnName.endsWith('_id')) {
        const prefix = lowerColumnName.slice(0, -3)
        const variations = [prefix, prefix + 's', prefix.slice(0, -1)]
        
        if (variations.includes(lowerTableName)) {
          const targetTable = this.tables.get(tableName)
          if (targetTable?.columns.some(col => col.name.toLowerCase() === 'id')) {
            references.push({ tableName, columnName: 'id' })
          }
        }
      }
    }
    
    return references
  }

  private areColumnsCompatible(col1: Column, col2: Column): boolean {
    const type1 = col1.type.toLowerCase().replace(/\([^)]*\)/g, '')
    const type2 = col2.type.toLowerCase().replace(/\([^)]*\)/g, '')
    
    const integerTypes = ['int', 'integer', 'bigint', 'smallint', 'serial', 'bigserial']
    const stringTypes = ['varchar', 'char', 'text', 'string']
    
    return (
      (integerTypes.includes(type1) && integerTypes.includes(type2)) ||
      (stringTypes.includes(type1) && stringTypes.includes(type2)) ||
      type1 === type2
    )
  }
}