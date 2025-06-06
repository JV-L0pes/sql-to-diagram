// src/lib/sqlParser.ts
import { Table, Column, Relationship, DatabaseSchema } from '@/types/Table'

interface ParsedConstraint {
  type: 'PRIMARY_KEY' | 'FOREIGN_KEY' | 'UNIQUE' | 'CHECK'
  columns: string[]
  referencedTable?: string
  referencedColumns?: string[]
  name?: string
}

interface TableMetadata {
  table: Table
  constraints: ParsedConstraint[]
  indexes: string[][]
}

export class SQLParser {
  private tables: Map<string, TableMetadata> = new Map()
  private relationships: Relationship[] = []
  private junctionTables: Set<string> = new Set()

  parseSQLScript(sqlScript: string): DatabaseSchema {
    this.tables.clear()
    this.relationships = []
    this.junctionTables.clear()

    try {
      this.parseSQL(sqlScript)
      this.identifyJunctionTables()
      this.detectAllRelationships()
      this.optimizeRelationships()
    } catch (error) {
      console.error('SQL parsing failed:', error)
    }

    return {
      tables: Array.from(this.tables.values()).map(meta => meta.table),
      relationships: this.relationships
    }
  }

  private parseSQL(sqlScript: string): void {
    const statements = this.splitStatements(sqlScript)
    
    for (const statement of statements) {
      const trimmed = statement.trim()
      const upperStatement = trimmed.toUpperCase()
      
      if (upperStatement.startsWith('CREATE TABLE')) {
        this.parseCreateTable(trimmed)
      } else if (upperStatement.startsWith('ALTER TABLE')) {
        this.parseAlterTable(trimmed)
      } else if (upperStatement.startsWith('CREATE INDEX') || upperStatement.startsWith('CREATE UNIQUE INDEX')) {
        this.parseCreateIndex(trimmed)
      }
    }
  }

  private splitStatements(sql: string): string[] {
    sql = sql.replace(/--.*$/gm, '')
    sql = sql.replace(/\/\*[\s\S]*?\*\//g, '')
    
    const statements: string[] = []
    let current = ''
    let inQuotes = false
    let quoteChar = ''
    
    for (let i = 0; i < sql.length; i++) {
      const char = sql[i]
      
      if (!inQuotes && (char === '"' || char === "'" || char === '`')) {
        inQuotes = true
        quoteChar = char
      } else if (inQuotes && char === quoteChar) {
        inQuotes = false
        quoteChar = ''
      } else if (!inQuotes && char === ';') {
        if (current.trim()) {
          statements.push(current.trim())
        }
        current = ''
        continue
      }
      
      current += char
    }
    
    if (current.trim()) {
      statements.push(current.trim())
    }
    
    return statements
  }

  private parseCreateTable(statement: string): void {
    const tableNameMatch = statement.match(/CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)/i)
    if (!tableNameMatch) return

    const tableName = tableNameMatch[1]
    const contentMatch = statement.match(/\(([\s\S]*)\)/)
    if (!contentMatch) return

    const content = contentMatch[1]
    const definitions = this.splitTableDefinitions(content)
    
    const columns: Column[] = []
    const constraints: ParsedConstraint[] = []
    
    for (const definition of definitions) {
      const trimmed = definition.trim()
      const upperDef = trimmed.toUpperCase()
      
      if (upperDef.startsWith('PRIMARY KEY')) {
        constraints.push(this.parsePrimaryKeyConstraint(trimmed))
      } else if (upperDef.startsWith('FOREIGN KEY')) {
        constraints.push(this.parseForeignKeyConstraint(trimmed))
      } else if (upperDef.startsWith('UNIQUE')) {
        constraints.push(this.parseUniqueConstraint(trimmed))
      } else if (upperDef.startsWith('CHECK')) {
        constraints.push(this.parseCheckConstraint(trimmed))
      } else if (upperDef.startsWith('CONSTRAINT')) {
        const constraint = this.parseNamedConstraint(trimmed)
        if (constraint) constraints.push(constraint)
      } else if (trimmed.length > 0) {
        const column = this.parseColumnDefinition(trimmed)
        if (column) columns.push(column)
      }
    }

    // Apply primary key constraints
    const pkConstraint = constraints.find(c => c.type === 'PRIMARY_KEY')
    if (pkConstraint) {
      pkConstraint.columns.forEach(colName => {
        const column = columns.find(c => c.name === colName)
        if (column) column.primaryKey = true
      })
    }

    // Apply foreign key relationships to columns
    constraints.filter(c => c.type === 'FOREIGN_KEY').forEach(fkConstraint => {
      fkConstraint.columns.forEach(colName => {
        const column = columns.find(c => c.name === colName)
        if (column && fkConstraint.referencedTable && fkConstraint.referencedColumns) {
          column.foreignKey = {
            table: fkConstraint.referencedTable,
            column: fkConstraint.referencedColumns[0]
          }
        }
      })
    })

    this.tables.set(tableName, {
      table: { name: tableName, columns },
      constraints,
      indexes: []
    })
  }

  private splitTableDefinitions(content: string): string[] {
    const definitions: string[] = []
    let current = ''
    let parenDepth = 0
    let inQuotes = false
    let quoteChar = ''
    
    for (let i = 0; i < content.length; i++) {
      const char = content[i]
      
      if (!inQuotes && (char === '"' || char === "'" || char === '`')) {
        inQuotes = true
        quoteChar = char
      } else if (inQuotes && char === quoteChar) {
        inQuotes = false
        quoteChar = ''
      } else if (!inQuotes) {
        if (char === '(') {
          parenDepth++
        } else if (char === ')') {
          parenDepth--
        } else if (char === ',' && parenDepth === 0) {
          definitions.push(current.trim())
          current = ''
          continue
        }
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

  private parsePrimaryKeyConstraint(definition: string): ParsedConstraint {
    const match = definition.match(/PRIMARY\s+KEY\s*\(([^)]+)\)/i)
    const columns = match ? match[1].split(',').map(col => col.trim().replace(/["`]/g, '')) : []
    
    return {
      type: 'PRIMARY_KEY',
      columns
    }
  }

  private parseForeignKeyConstraint(definition: string): ParsedConstraint {
    const match = definition.match(/FOREIGN\s+KEY\s*\(([^)]+)\)\s+REFERENCES\s+(\w+)\s*\(([^)]+)\)/i)
    
    if (match) {
      const columns = match[1].split(',').map(col => col.trim().replace(/["`]/g, ''))
      const referencedTable = match[2].trim()
      const referencedColumns = match[3].split(',').map(col => col.trim().replace(/["`]/g, ''))
      
      return {
        type: 'FOREIGN_KEY',
        columns,
        referencedTable,
        referencedColumns
      }
    }
    
    return { type: 'FOREIGN_KEY', columns: [] }
  }

  private parseUniqueConstraint(definition: string): ParsedConstraint {
    const match = definition.match(/UNIQUE\s*\(([^)]+)\)/i)
    const columns = match ? match[1].split(',').map(col => col.trim().replace(/["`]/g, '')) : []
    
    return {
      type: 'UNIQUE',
      columns
    }
  }

  private parseCheckConstraint(definition: string): ParsedConstraint {
    return {
      type: 'CHECK',
      columns: []
    }
  }

  private parseNamedConstraint(definition: string): ParsedConstraint | null {
    const constraintMatch = definition.match(/CONSTRAINT\s+(\w+)\s+(.*)/i)
    if (!constraintMatch) return null
    
    const constraintName = constraintMatch[1]
    const constraintDef = constraintMatch[2]
    const upperDef = constraintDef.toUpperCase()
    
    if (upperDef.startsWith('PRIMARY KEY')) {
      const constraint = this.parsePrimaryKeyConstraint(constraintDef)
      constraint.name = constraintName
      return constraint
    } else if (upperDef.startsWith('FOREIGN KEY')) {
      const constraint = this.parseForeignKeyConstraint(constraintDef)
      constraint.name = constraintName
      return constraint
    } else if (upperDef.startsWith('UNIQUE')) {
      const constraint = this.parseUniqueConstraint(constraintDef)
      constraint.name = constraintName
      return constraint
    }
    
    return null
  }

  private parseAlterTable(statement: string): void {
    const tableMatch = statement.match(/ALTER\s+TABLE\s+(\w+)/i)
    if (!tableMatch) return
    
    const tableName = tableMatch[1]
    const tableMeta = this.tables.get(tableName)
    if (!tableMeta) return
    
    if (statement.toUpperCase().includes('ADD CONSTRAINT')) {
      const constraintMatch = statement.match(/ADD\s+CONSTRAINT\s+(\w+)\s+(.*)/i)
      if (constraintMatch) {
        const constraint = this.parseNamedConstraint(`CONSTRAINT ${constraintMatch[1]} ${constraintMatch[2]}`)
        if (constraint) {
          tableMeta.constraints.push(constraint)
        }
      }
    }
  }

  private parseCreateIndex(statement: string): void {
    const match = statement.match(/CREATE\s+(?:UNIQUE\s+)?INDEX\s+\w+\s+ON\s+(\w+)\s*\(([^)]+)\)/i)
    if (!match) return
    
    const tableName = match[1]
    const columns = match[2].split(',').map(col => col.trim().replace(/["`]/g, ''))
    
    const tableMeta = this.tables.get(tableName)
    if (tableMeta) {
      tableMeta.indexes.push(columns)
    }
  }

  private identifyJunctionTables(): void {
    for (const [tableName, meta] of this.tables) {
      const fkConstraints = meta.constraints.filter(c => c.type === 'FOREIGN_KEY')
      
      // Junction table criteria:
      // 1. Has exactly 2 foreign keys
      // 2. Primary key includes both foreign key columns
      // 3. No other significant columns
      if (fkConstraints.length === 2) {
        const pkConstraint = meta.constraints.find(c => c.type === 'PRIMARY_KEY')
        const allFkColumns = fkConstraints.flatMap(fk => fk.columns)
        
        if (pkConstraint && 
            pkConstraint.columns.length === allFkColumns.length &&
            pkConstraint.columns.every(col => allFkColumns.includes(col))) {
          
          // Check if table has minimal additional columns
          const nonFkColumns = meta.table.columns.filter(col => 
            !allFkColumns.includes(col.name) && 
            !['id', 'created_at', 'updated_at', 'deleted_at'].includes(col.name.toLowerCase())
          )
          
          if (nonFkColumns.length <= 2) {
            this.junctionTables.add(tableName)
          }
        }
      }
    }
  }

  private detectAllRelationships(): void {
    // First pass: Direct foreign key relationships
    for (const [tableName, meta] of this.tables) {
      const fkConstraints = meta.constraints.filter(c => c.type === 'FOREIGN_KEY')
      
      for (const fkConstraint of fkConstraints) {
        if (!fkConstraint.referencedTable || !fkConstraint.referencedColumns) continue
        
        for (let i = 0; i < fkConstraint.columns.length; i++) {
          const sourceColumn = fkConstraint.columns[i]
          const targetColumn = fkConstraint.referencedColumns[i]
          
          if (!this.junctionTables.has(tableName)) {
            const relationshipType = this.determineRelationshipType(
              tableName, sourceColumn, fkConstraint.referencedTable, targetColumn
            )
            
            this.relationships.push({
              from: { table: tableName, column: sourceColumn },
              to: { table: fkConstraint.referencedTable, column: targetColumn },
              type: relationshipType
            })
          }
        }
      }
    }
    
    // Second pass: Many-to-many through junction tables
    for (const junctionTableName of this.junctionTables) {
      this.processManyToManyRelationship(junctionTableName)
    }
    
    // Third pass: Convention-based relationships
    this.detectConventionBasedRelationships()
  }

  private determineRelationshipType(
    sourceTable: string, 
    sourceColumn: string, 
    targetTable: string, 
    targetColumn: string
  ): 'ONE_TO_ONE' | 'ONE_TO_MANY' | 'MANY_TO_ONE' | 'MANY_TO_MANY' {
    
    const sourceMeta = this.tables.get(sourceTable)
    const targetMeta = this.tables.get(targetTable)
    
    if (!sourceMeta || !targetMeta) return 'MANY_TO_ONE'
    
    // Check if source column is unique (ONE_TO_ONE or ONE_TO_MANY)
    const sourceIsUnique = this.isColumnUnique(sourceMeta, sourceColumn)
    const targetIsUnique = this.isColumnUnique(targetMeta, targetColumn)
    
    if (sourceIsUnique && targetIsUnique) {
      return 'ONE_TO_ONE'
    } else if (sourceIsUnique) {
      return 'ONE_TO_ONE' // Source can only reference one target
    } else if (targetIsUnique) {
      return 'MANY_TO_ONE' // Many sources can reference one target
    } else {
      return 'MANY_TO_ONE' // Default case
    }
  }

  private isColumnUnique(tableMeta: TableMetadata, columnName: string): boolean {
    // Check unique constraints
    const uniqueConstraints = tableMeta.constraints.filter(c => c.type === 'UNIQUE')
    const isSingleColumnUnique = uniqueConstraints.some(constraint => 
      constraint.columns.length === 1 && constraint.columns[0] === columnName
    )
    
    // Check primary key
    const pkConstraints = tableMeta.constraints.filter(c => c.type === 'PRIMARY_KEY')
    const isSingleColumnPK = pkConstraints.some(constraint =>
      constraint.columns.length === 1 && constraint.columns[0] === columnName
    )
    
    // Check column-level unique
    const column = tableMeta.table.columns.find(c => c.name === columnName)
    
    return isSingleColumnUnique || isSingleColumnPK || (column?.primaryKey === true)
  }

  private processManyToManyRelationship(junctionTableName: string): void {
    const junctionMeta = this.tables.get(junctionTableName)
    if (!junctionMeta) return
    
    const fkConstraints = junctionMeta.constraints.filter(c => c.type === 'FOREIGN_KEY')
    if (fkConstraints.length !== 2) return
    
    const [fk1, fk2] = fkConstraints
    if (!fk1.referencedTable || !fk2.referencedTable) return
    
    // Create bidirectional many-to-many relationship
    this.relationships.push({
      from: { table: fk1.referencedTable, column: fk1.referencedColumns![0] },
      to: { table: fk2.referencedTable, column: fk2.referencedColumns![0] },
      type: 'MANY_TO_MANY'
    })
    
    this.relationships.push({
      from: { table: fk2.referencedTable, column: fk2.referencedColumns![0] },
      to: { table: fk1.referencedTable, column: fk1.referencedColumns![0] },
      type: 'MANY_TO_MANY'
    })
  }

  private detectConventionBasedRelationships(): void {
    const tableNames = Array.from(this.tables.keys())
    
    for (const [tableName, meta] of this.tables) {
      if (this.junctionTables.has(tableName)) continue
      
      for (const column of meta.table.columns) {
        if (column.foreignKey) continue
        
        const possibleReferences = this.findConventionBasedReferences(column.name, tableNames, tableName)
        
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
              const refColumn = refTable.table.columns.find(col => col.name === ref.columnName)
              if (refColumn && this.areColumnsCompatible(column, refColumn)) {
                const relationshipType = this.determineRelationshipType(
                  tableName, column.name, ref.tableName, ref.columnName
                )
                
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

  private findConventionBasedReferences(
    columnName: string, 
    tableNames: string[], 
    currentTable: string
  ): Array<{tableName: string, columnName: string}> {
    const references: Array<{tableName: string, columnName: string}> = []
    const lowerColumnName = columnName.toLowerCase()
    
    for (const tableName of tableNames) {
      if (tableName === currentTable || this.junctionTables.has(tableName)) continue
      
      const lowerTableName = tableName.toLowerCase()
      
      // Pattern: user_id -> users.id, categoria_id -> categorias.id
      if (lowerColumnName.endsWith('_id')) {
        const prefix = lowerColumnName.slice(0, -3)
        const variations = [
          prefix,
          prefix + 's',
          prefix + 'es', 
          prefix.slice(0, -1), // Remove 's' from plural
          prefix.replace(/s$/, ''), // Remove trailing 's'
          prefix + 'a', // categoria -> categoria_id
          prefix + 'as' // categoria -> categorias
        ]
        
        if (variations.includes(lowerTableName)) {
          const targetTable = this.tables.get(tableName)
          if (targetTable?.table.columns.some(col => col.name.toLowerCase() === 'id')) {
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
    
    const integerTypes = ['int', 'integer', 'bigint', 'smallint', 'serial', 'bigserial', 'tinyint', 'mediumint']
    const stringTypes = ['varchar', 'char', 'text', 'string', 'nvarchar', 'nchar']
    const decimalTypes = ['decimal', 'numeric', 'float', 'double', 'real', 'money']
    const dateTypes = ['date', 'datetime', 'timestamp', 'time']
    
    const getTypeCategory = (type: string) => {
      if (integerTypes.includes(type)) return 'integer'
      if (stringTypes.includes(type)) return 'string'
      if (decimalTypes.includes(type)) return 'decimal'
      if (dateTypes.includes(type)) return 'date'
      return type
    }
    
    return getTypeCategory(type1) === getTypeCategory(type2)
  }

  private optimizeRelationships(): void {
    // Remove duplicate relationships
    const uniqueRelationships = new Map<string, Relationship>()
    
    for (const relationship of this.relationships) {
      const key = `${relationship.from.table}.${relationship.from.column}->${relationship.to.table}.${relationship.to.column}`
      
      if (!uniqueRelationships.has(key)) {
        uniqueRelationships.set(key, relationship)
      }
    }
    
    this.relationships = Array.from(uniqueRelationships.values())
    
    // Sort relationships by type priority
    const typePriority = {
      'ONE_TO_ONE': 0,
      'ONE_TO_MANY': 1,
      'MANY_TO_ONE': 2,
      'MANY_TO_MANY': 3
    }
    
    this.relationships.sort((a, b) => {
      const priorityDiff = typePriority[a.type] - typePriority[b.type]
      if (priorityDiff !== 0) return priorityDiff
      
      return `${a.from.table}.${a.from.column}`.localeCompare(`${b.from.table}.${b.from.column}`)
    })
  }
}