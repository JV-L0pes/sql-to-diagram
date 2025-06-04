// src/lib/sqlParser.ts - Enhanced Version
import { Table, Column, Relationship, DatabaseSchema } from '@/types/Table'

export class SQLParser {
  private tables: Map<string, Table> = new Map()
  private relationships: Relationship[] = []
  private primaryKeys: Map<string, string[]> = new Map()
  private foreignKeys: Map<string, { column: string; refTable: string; refColumn: string }[]> = new Map()
  private uniqueConstraints: Map<string, string[]> = new Map()

  parseSQLScript(sqlScript: string): DatabaseSchema {
    this.tables.clear()
    this.relationships = []
    this.primaryKeys.clear()
    this.foreignKeys.clear()
    this.uniqueConstraints.clear()

    try {
      this.parseSQL(sqlScript)
      this.analyzeRelationships()
    } catch (error) {
      console.error('SQL parsing failed:', error)
    }

    return {
      tables: Array.from(this.tables.values()),
      relationships: this.relationships
    }
  }

  private parseSQL(sqlScript: string): void {
    const statements = this.splitStatements(sqlScript)
    
    for (const statement of statements) {
      this.processStatement(statement.trim())
    }
  }

  private splitStatements(sql: string): string[] {
    // Remove comentários
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

    const tableName = tableNameMatch[1].toLowerCase()
    const contentMatch = statement.match(/\(([\s\S]*)\)/)
    if (!contentMatch) return

    const content = contentMatch[1]
    const columnDefinitions = this.splitColumnDefinitions(content)
    
    const columns: Column[] = []
    const tablePrimaryKeys: string[] = []
    const tableForeignKeys: { column: string; refTable: string; refColumn: string }[] = []
    const tableUniqueConstraints: string[] = []
    
    for (const definition of columnDefinitions) {
      const trimmed = definition.trim()
      
      if (trimmed.toUpperCase().startsWith('PRIMARY KEY')) {
        const pkMatch = trimmed.match(/PRIMARY\s+KEY\s*\(([^)]+)\)/i)
        if (pkMatch) {
          const pkColumns = pkMatch[1].split(',').map(col => col.trim().replace(/["`]/g, '').toLowerCase())
          tablePrimaryKeys.push(...pkColumns)
        }
      } else if (trimmed.toUpperCase().startsWith('FOREIGN KEY')) {
        this.parseForeignKeyConstraint(trimmed, tableForeignKeys)
      } else if (trimmed.toUpperCase().startsWith('UNIQUE')) {
        this.parseUniqueConstraint(trimmed, tableUniqueConstraints)
      } else if (trimmed.length > 0 && !trimmed.toUpperCase().startsWith('CONSTRAINT')) {
        const column = this.parseColumnDefinition(trimmed)
        if (column) {
          columns.push(column)
          
          // Check for inline constraints
          if (column.primaryKey) {
            tablePrimaryKeys.push(column.name)
          }
          if (column.foreignKey) {
            tableForeignKeys.push({
              column: column.name,
              refTable: column.foreignKey.table,
              refColumn: column.foreignKey.column
            })
          }
          if (this.hasUniqueConstraint(trimmed)) {
            tableUniqueConstraints.push(column.name)
          }
        }
      }
    }

    // Store metadata
    this.primaryKeys.set(tableName, tablePrimaryKeys)
    this.foreignKeys.set(tableName, tableForeignKeys)
    this.uniqueConstraints.set(tableName, tableUniqueConstraints)

    // Mark primary keys in columns
    columns.forEach(column => {
      if (tablePrimaryKeys.includes(column.name.toLowerCase())) {
        column.primaryKey = true
      }
    })

    // Mark foreign keys in columns
    tableForeignKeys.forEach(fk => {
      const column = columns.find(col => col.name.toLowerCase() === fk.column.toLowerCase())
      if (column) {
        column.foreignKey = {
          table: fk.refTable,
          column: fk.refColumn
        }
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

    const name = parts[0].replace(/["`]/g, '').toLowerCase()
    const type = parts[1]
    const upperDef = definition.toUpperCase()
    
    return {
      name,
      type,
      nullable: !upperDef.includes('NOT NULL'),
      primaryKey: upperDef.includes('PRIMARY KEY')
    }
  }

  private parseForeignKeyConstraint(definition: string, foreignKeys: { column: string; refTable: string; refColumn: string }[]): void {
    const fkMatch = definition.match(/FOREIGN\s+KEY\s*\(([^)]+)\)\s+REFERENCES\s+(\w+)\s*\(([^)]+)\)/i)
    
    if (fkMatch) {
      const sourceColumns = fkMatch[1].split(',').map(col => col.trim().replace(/["`]/g, '').toLowerCase())
      const targetTable = fkMatch[2].trim().toLowerCase()
      const targetColumns = fkMatch[3].split(',').map(col => col.trim().replace(/["`]/g, '').toLowerCase())
      
      // Handle multi-column foreign keys
      sourceColumns.forEach((sourceCol, index) => {
        const targetCol = targetColumns[index] || targetColumns[0]
        foreignKeys.push({
          column: sourceCol,
          refTable: targetTable,
          refColumn: targetCol
        })
      })
    }
  }

  private parseUniqueConstraint(definition: string, uniqueConstraints: string[]): void {
    const uniqueMatch = definition.match(/UNIQUE\s*\(([^)]+)\)/i)
    if (uniqueMatch) {
      const columns = uniqueMatch[1].split(',').map(col => col.trim().replace(/["`]/g, '').toLowerCase())
      uniqueConstraints.push(...columns)
    }
  }

  private hasUniqueConstraint(definition: string): boolean {
    return definition.toUpperCase().includes('UNIQUE')
  }

  private analyzeRelationships(): void {
    const junctionTables = this.identifyJunctionTables()
    
    // Process junction tables first (MANY_TO_MANY)
    junctionTables.forEach(junction => {
      this.createManyToManyRelationship(junction)
    })

    // Process remaining foreign keys
    for (const [tableName, foreignKeys] of this.foreignKeys) {
      if (junctionTables.has(tableName)) continue // Skip junction tables
      
      foreignKeys.forEach(fk => {
        const relationshipType = this.determineRelationshipType(tableName, fk.column, fk.refTable, fk.refColumn)
        
        this.relationships.push({
          from: { table: tableName, column: fk.column },
          to: { table: fk.refTable, column: fk.refColumn },
          type: relationshipType
        })
      })
    }

    // Detect relationships by convention (for tables without explicit FKs)
    this.detectConventionBasedRelationships()
  }

  private identifyJunctionTables(): Set<string> {
    const junctionTables = new Set<string>()
    
    for (const [tableName, foreignKeys] of this.foreignKeys) {
      const table = this.tables.get(tableName)
      if (!table) continue

      // Junction table criteria:
      // 1. Has exactly 2 foreign keys
      // 2. Primary key consists of those 2 foreign key columns
      // 3. Has minimal additional columns (typically just the FKs and maybe timestamps)
      
      if (foreignKeys.length === 2) {
        const primaryKeys = this.primaryKeys.get(tableName) || []
        const fkColumns = foreignKeys.map(fk => fk.column.toLowerCase())
        
        // Check if PK consists of exactly the 2 FK columns
        const isPrimaryKeyComposite = primaryKeys.length === 2 && 
          primaryKeys.every(pk => fkColumns.includes(pk.toLowerCase()))
        
        // Check if table has minimal additional columns
        const nonFkColumns = table.columns.filter(col => 
          !fkColumns.includes(col.name.toLowerCase()) && 
          !this.isTimestampColumn(col.name)
        )
        
        if (isPrimaryKeyComposite && nonFkColumns.length <= 2) {
          junctionTables.add(tableName)
        }
      }
    }
    
    return junctionTables
  }

  private isTimestampColumn(columnName: string): boolean {
    const timestampPatterns = ['created_at', 'updated_at', 'deleted_at', 'timestamp', 'date_created', 'date_modified']
    return timestampPatterns.some(pattern => columnName.toLowerCase().includes(pattern))
  }

  private createManyToManyRelationship(junctionTableName: string): void {
    const foreignKeys = this.foreignKeys.get(junctionTableName)
    if (!foreignKeys || foreignKeys.length !== 2) return

    const [fk1, fk2] = foreignKeys

    // Create bidirectional MANY_TO_MANY relationship
    this.relationships.push({
      from: { table: fk1.refTable, column: fk1.refColumn },
      to: { table: fk2.refTable, column: fk2.refColumn },
      type: 'MANY_TO_MANY',
      junctionTable: junctionTableName
    })
  }

  private determineRelationshipType(
    fromTable: string, 
    fromColumn: string, 
    toTable: string, 
    toColumn: string
  ): 'ONE_TO_ONE' | 'ONE_TO_MANY' | 'MANY_TO_ONE' | 'MANY_TO_MANY' {
    
    // Check if the foreign key column has a unique constraint
    const fromTableUniqueConstraints = this.uniqueConstraints.get(fromTable) || []
    const isFromColumnUnique = fromTableUniqueConstraints.includes(fromColumn.toLowerCase())
    
    // Check if the referenced column is a primary key
    const toTablePrimaryKeys = this.primaryKeys.get(toTable) || []
    const isToColumnPrimary = toTablePrimaryKeys.includes(toColumn.toLowerCase())
    
    // Determine relationship type
    if (isFromColumnUnique && isToColumnPrimary) {
      return 'ONE_TO_ONE'
    } else if (isToColumnPrimary) {
      return 'MANY_TO_ONE'
    } else {
      // Non-primary key reference, less common
      return 'MANY_TO_ONE'
    }
  }

  private detectConventionBasedRelationships(): void {
    const tableNames = Array.from(this.tables.keys())
    
    for (const [tableName, table] of this.tables) {
      for (const column of table.columns) {
        // Skip if already has explicit foreign key
        if (column.foreignKey) continue
        
        const possibleReferences = this.findPossibleReferences(column.name, tableNames, tableName)
        
        for (const ref of possibleReferences) {
          // Check if relationship already exists
          const relationshipExists = this.relationships.some(rel => 
            rel.from.table === tableName && 
            rel.from.column === column.name &&
            rel.to.table === ref.tableName &&
            rel.to.column === ref.columnName
          )
          
          if (!relationshipExists) {
            const refTable = this.tables.get(ref.tableName)
            if (refTable) {
              const refColumn = refTable.columns.find(col => col.name.toLowerCase() === ref.columnName.toLowerCase())
              if (refColumn && this.areColumnsCompatible(column, refColumn)) {
                const relationshipType = this.determineRelationshipType(tableName, column.name, ref.tableName, ref.columnName)
                
                this.relationships.push({
                  from: { table: tableName, column: column.name },
                  to: { table: ref.tableName, column: ref.columnName },
                  type: relationshipType
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
        const variations = [
          prefix,           // user -> user
          prefix + 's',     // user -> users  
          prefix.slice(0, -1) // users -> user (remove 's')
        ]
        
        if (variations.includes(lowerTableName)) {
          const targetTable = this.tables.get(tableName)
          if (targetTable?.columns.some(col => col.name.toLowerCase() === 'id')) {
            references.push({ tableName, columnName: 'id' })
          }
        }
      }
      
      // Pattern: usuario_id -> usuarios.id (handle Portuguese/Spanish)
      if (lowerColumnName.includes('_id')) {
        const parts = lowerColumnName.split('_')
        if (parts[parts.length - 1] === 'id') {
          const prefix = parts.slice(0, -1).join('_')
          if (lowerTableName.includes(prefix) || prefix.includes(lowerTableName)) {
            const targetTable = this.tables.get(tableName)
            if (targetTable?.columns.some(col => col.name.toLowerCase() === 'id')) {
              references.push({ tableName, columnName: 'id' })
            }
          }
        }
      }
    }
    
    return references
  }

  private areColumnsCompatible(col1: Column, col2: Column): boolean {
    const type1 = col1.type.toLowerCase().replace(/\([^)]*\)/g, '')
    const type2 = col2.type.toLowerCase().replace(/\([^)]*\)/g, '')
    
    const integerTypes = ['int', 'integer', 'bigint', 'smallint', 'serial', 'bigserial', 'tinyint', 'mediumint']
    const stringTypes = ['varchar', 'char', 'text', 'string', 'nvarchar', 'nchar']
    const uuidTypes = ['uuid', 'uniqueidentifier']
    
    return (
      (integerTypes.includes(type1) && integerTypes.includes(type2)) ||
      (stringTypes.includes(type1) && stringTypes.includes(type2)) ||
      (uuidTypes.includes(type1) && uuidTypes.includes(type2)) ||
      type1 === type2
    )
  }
}